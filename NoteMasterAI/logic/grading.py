import os
import io
import json
import cv2
import numpy as np
from PIL import Image
from google.cloud import vision
import google.generativeai as genai
from logic import utils

# Global variables to act as a fallback for keys if needed, 
# although we prefer passing them or environment variables.
SERVICE_ACCOUNT_FILE = "service-account.json"

def setup_apis(api_key=None, service_account_path=None):
    """
    API anahtarlarını ayarlar.
    
    Args:
        api_key (str): Gemini API Key. If None, checks GEMINI_API_KEY env var.
        service_account_path (str): Path to service-account.json. If None, checks default or env var.
        
    Returns:
        (vision_client, gemini_model) tuple, or (None, None) on failure.
    """
    # 1. Google Cloud Vision (Göz)
    if service_account_path is None:
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            service_account_path = SERVICE_ACCOUNT_FILE
        else:
            # Check env var if file not found in CWD
            pass 
            
    if not service_account_path or not os.path.exists(service_account_path):
        print(f"HATA: Service account file bulunamadı: {service_account_path}")
        return None, None
    
    try:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path
        vision_client = vision.ImageAnnotatorClient()
    except Exception as e:
        print(f"Google Cloud Vision başlatılamadı: {e}")
        return None, None
    
    # 2. Gemini (Beyin)
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("HATA: `GEMINI_API_KEY` bulunamadı.")
        return None, None
            
    try:
        genai.configure(api_key=api_key)
        # Using the same model as in app.py
        gemini_model = genai.GenerativeModel("gemini-3-flash-preview") 
    except Exception as e:
        print(f"HATA: Gemini API anahtarı okunamadı: {e}")
        return None, None
        
    print("Google Cloud Vision ve Gemini API başarıyla ayarlandı.")
    return vision_client, gemini_model

def get_text_from_image(_vision_client, image_cv2):
    """
    Bir CV2 görüntüsü alır, Google Cloud Vision HTR
    ile okur ve algılanan metni döndürür.
    """
    if image_cv2 is None:
        return ""
        
    try:
        _, buffer = cv2.imencode('.jpg', image_cv2)
        image_bytes = buffer.tobytes()
        
        image = vision.Image(content=image_bytes)
        response = _vision_client.document_text_detection(image=image)
        
        if response.error.message:
            print(f"Cloud Vision Hatası: {response.error.message}")
            return ""
            
        return response.full_text_annotation.text
        
    except Exception as e:
        print(f"Cloud Vision API çağrılırken hata: {e}")
        return ""

def get_gemini_score(_gemini_model, ogrenci_metni, ideal_metin, baglam_metni, soru_tipi, sorunun_gorseli=None, ogrenci_gorseli=None, teacher_prompt="", question_prompt="", preprocess=True):
    """
    Öğrenci cevabını puanlar.
    
    Args:
        sorunun_gorseli (PIL.Image or bytes, optional): Sorunun orijinal metnini/görselini içeren kırpılmış alan.
        ogrenci_gorseli (PIL.Image, optional): Öğrencinin cevabını içeren görsel (crop).
    """
    
    # 1. Base Prompt with Relaxed Rules
    system_prompt = f"""
Sen, "NoteMaster" adlı adil, dikkatli ve öğrenci dostu bir öğretmen yapay zekasısın.

*** 1. GÖRSEL ALGILAMA VE HALÜSİNASYON (REALITY CHECK) ***
Cevap anahtarı senin algını kör etmesin. Gözlerinle gördüğün gerçeği inkar etme.
*   **SENARYO:** Cevap Anahtarı "5" diyor. Görselde net bir "31" veya "(31)" veya "A" var.
*   **HATALI TEPKİ:** "Öğrenci 5 yazmış, harika." (BUNU YAPARSAN SİSTEM ÇÖKER!)
*   **DOĞRU TEPKİ:** "Okunan: 31. Puan: 0. Gerekçe: Öğrenci 31 yazmış ama cevap 5."
*   **KURAL:** Görseldeki metin, cevap anahtarından farklıysa, ASLA "aslında doğru yazmak istedi" diye düşünme. Ne görüyorsan onu raporla.

*** 2. KISMİ PUANLAMA (PARTIAL CREDIT) - ÇOK ÖNEMLİ ***
Öğrencinin tek bir hatası yüzünden tüm emeğini çöpe atma.
*   **Çok Maddeli Sorular (Tablo, Boşluk Doldurma, Eşleştirme):**
    *   Eğer soruda birden fazla alt cevap varsa (örn: Tabloda 4 kutucuk işaretlenecekse), başarı oranına göre puan ver.
    *   Örnek: 4 maddeden 3'ü doğru, 1'i yanlış. -> Başarı %75. -> **Puan: 0.75** (veya 0.50). ASLA 0.0 VERME!
    *   Örnek: 10 maddelik tablo, 1 hata var. -> Başarı %90. -> **Puan: 1.0** (Küçük hataları affet) veya **0.75**.
*   **AI Çözsün Soruları:**
    *   Bu sorularda "Ya Hep Ya Hiç" kuralı YOKTUR. Doğru gidiş yollarına, kısmi doğrulara puan ver.

*** 3. OKUMA VE YORUMLAMA ***
*   **OCR:** [OCR Metni] bazen saçmalar. Görseldeki el yazısı esastır.
*   **Niyet Okuma:** "Nolur puan ver" gibi yazılar CEVAP DEĞİLDİR. Bunlara 0 ver.

**JSON Çıktı Formatı:**
{{
    "okunan_cevap": "Görselde görülen metin (Yorum katma)",
    "puan": [0.0, 0.25, 0.50, 0.75, 1.0], 
    "gerekce": "Kısa açıklama (Örn: '3 madde doğru, 1 yanlış. Kısmi puan.')",
    "kendi_bilgisi_kullanildi": false
}}

*** 4. ÖZEL TALİMATLAR ***
*   **[GENEL ÖĞRETMEN NOTU]:** "{teacher_prompt}" 
    > (Eğer öğretmenin bu notunda özel bir talimat varsa, yukarıdaki kuralları esnetebilirsin. Örneğin 'Yazım yanlışlarını görmezden gel' derse, puan kırma.)
*   **[SORUYA ÖZEL NOT]:** "{question_prompt}"
    > (Bu soru için özel bir kriter belirtilmişse, buna KESİNLİKLE uy.)

---
[SORU TİPİ]: {soru_tipi}
[CEVAP ANAHTARI]: {ideal_metin}
[DERS NOTLARI]: {baglam_metni}
    """

    # 2. Add Content Parts
    content_parts = [system_prompt]
    
    # Add Question Context Image if available
    if sorunun_gorseli:
        # Preprocess? Maybe not context, but let's keep it readable
        content_parts.append("\n\n[SORUNUN KENDİSİ (BAĞLAM GÖRSELİ)]:")
        content_parts.append(sorunun_gorseli)
        
    # Add Student Answer Image (CRITICAL UPDATE)
    if ogrenci_gorseli:
        # Convert PIL to CV2 for preprocessing
        cv_img = cv2.cvtColor(np.array(ogrenci_gorseli), cv2.COLOR_RGB2BGR)
        processed_cv = utils.preprocess_for_gemini(cv_img)
        processed_pil = Image.fromarray(cv2.cvtColor(processed_cv, cv2.COLOR_BGR2RGB))
        
        content_parts.append("\n\n[ÖĞRENCİ CEVABI GÖRSELİ (Bunun içindeki yazıyı oku)]:")
        content_parts.append(processed_pil)
        
    content_parts.append(f"\n\n[ÖĞRENCİ CEVABI (OCR Metni - Hatalı olabilir)]:\n{ogrenci_metni}")
    
    # 3. Call Gemini
    try:
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json"
        )
        response = _gemini_model.generate_content(
            content_parts,
            generation_config=generation_config
        )
        
        json_output = json.loads(response.text)
        
        # FIX: Handle list response (Gemini sometimes returns [{}])
        if isinstance(json_output, list):
            if len(json_output) > 0 and isinstance(json_output[0], dict):
                json_output = json_output[0]
            else:
                # Fallback if list structure is unexpected
                json_output = {
                    "okunan_cevap": ogrenci_metni, 
                    "puan": 0.0, 
                    "gerekce": "AI yanıtı anlaşılamadı (Liste formatı)", 
                    "kendi_bilgisi_kullanildi": False
                }

        if not isinstance(json_output, dict):
             raise ValueError(f"AI yanıtı beklenen formatta değil: {type(json_output)}")

        # Safety for Student Info
        if soru_tipi == "Öğrenci Bilgisi":
            json_output["puan"] = 0.0
            
        return json_output

    except Exception as e:
        print(f"Gemini API hatası: {e}")
        try:
            print(f"Gemini Ham Yanıtı: {response.prompt_feedback}")
        except:
            pass
        
        return {
            "okunan_cevap": ogrenci_metni,
            "puan": 0.0,
            "gerekce": f"Hata: {str(e)}",
            "kendi_bilgisi_kullanildi": False
        }

    # 2. Add Content Parts
    content_parts = [system_prompt]
    
    # Add Question Context Image if available
    if sorunun_gorseli:
        # Preprocess? Maybe not context, but let's keep it readable
        content_parts.append("\n\n[SORUNUN KENDİSİ (BAĞLAM GÖRSELİ)]:")
        content_parts.append(sorunun_gorseli)
        
    # Add Student Answer Image (CRITICAL UPDATE)
    if ogrenci_gorseli:
        # Convert PIL to CV2 for preprocessing
        cv_img = cv2.cvtColor(np.array(ogrenci_gorseli), cv2.COLOR_RGB2BGR)
        
        if preprocess:
             processed_cv = utils.preprocess_for_gemini(cv_img)
        else:
             processed_cv = cv_img    
             
        processed_pil = Image.fromarray(cv2.cvtColor(processed_cv, cv2.COLOR_BGR2RGB))
        
        content_parts.append("\n\n[ÖĞRENCİ CEVABI GÖRSELİ (Bunun içindeki yazıyı oku)]:")
        content_parts.append(processed_pil)
        
    content_parts.append(f"\n\n[ÖĞRENCİ CEVABI (OCR Metni - Hatalı olabilir)]:\n{ogrenci_metni}")

def get_ai_comparison_result(gemini_model, student_crop, key_crop, question_type="Çoktan Seçmeli", preprocess=True):
    """
    Compares Student Answer vs Key Answer using Gemini Vision.
    Returns: { "match": bool, "student_val": str, "key_val": str, "reason": str }
    """
    
    # Preprocess both
    s_cv = cv2.cvtColor(np.array(student_crop), cv2.COLOR_RGB2BGR)
    k_cv = cv2.cvtColor(np.array(key_crop), cv2.COLOR_RGB2BGR)
    
    if preprocess:
        s_proc = utils.preprocess_for_gemini(s_cv)
        k_proc = utils.preprocess_for_gemini(k_cv)
    else:
        s_proc = s_cv
        k_proc = k_cv
    
    s_pil = Image.fromarray(cv2.cvtColor(s_proc, cv2.COLOR_BGR2RGB))
    k_pil = Image.fromarray(cv2.cvtColor(k_proc, cv2.COLOR_BGR2RGB))
    
    prompt = f"""
    Sen keskin gözlü bir optik okuma asistanısın.
    Sana İKİ görsel veriyorum:
    1. [CEVAP ANAHTARI]: Doğru şıkkın temiz bir şekilde işaretlendiği referans.
    2. [ÖĞRENCİ CEVABI]: Öğrencinin sınav kağıdından kesilen parça.
    
    GÖREVİN:
    Öğrenci, Cevap Anahtarı ile AYNI seçeneği mi işaretlemiş?
    
    SORU TİPİ: {question_type}
    
    ANALİZ ADIMLARI:
    1. **Anahtar Tespiti**: Cevap Anahtarı görselinde hangi şıkkın (A, B, C, D, E veya Doğru/Yanlış) işaretli olduğunu bul. Bu senin REFERANSINDIR.
    2. **Öğrenci Tespiti**: Öğrenci görselinde hangi şıkkın işaretli olduğunu bul.
       - İşaretleme türü daire içine alma, çarpı (X), tik (✓) veya karalama olabilir.
       - Eğer öğrenci bir şıkkı işaretleyip sonra üzerini karalayıp BAŞKA bir şıkkı net bir şekilde işaretlediyse, SON KARARINI (net olanı) kabul et.
       - Silik veya çok hafif izleri "silinmiş" kabul et. En koyu ve belirgin işareti baz al.
    3. **Karşılaştırma**:
       - Tespit edilen [Öğrenci Cevabı] == [Referans] ise "match": true.
       - Değilse "match": false.
       - Öğrenci birden fazla şıkkı EŞİT derecede işaretlediyse (kararsız) "match": false döndür.
    
    ÇIKTI (Sadece JSON):
    {{
        "key_val": "Tespit edilen anahtar (Örn: 'C')",
        "student_val": "Tespit edilen öğrenci cevabı (Örn: 'A' veya 'C' veya 'BOŞ')",
        "match": true/false,
        "reason": "Kısa ve net açıklama (Örn: 'Anahtar C, Öğrenci A yapmış.' veya 'Öğrenci silip C yapmış, doğru.')"
    }}
    """
    
    try:
        response = gemini_model.generate_content([prompt, "CEVAP ANAHTARI:", k_pil, "ÖĞRENCİ CEVABI:", s_pil])
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"AI Comparison Error: {e}")
        return {"match": False, "student_val": "?", "key_val": "?", "reason": str(e)}

def parse_student_info(gemini_model, header_image_pil):
    """
    Uses Gemini to extract Name, Class, and Number from the header image.
    Returns: dict { 'name': str, 'class_name': str, 'number': str }
    """
    # Preprocess
    cv_img = cv2.cvtColor(np.array(header_image_pil), cv2.COLOR_RGB2BGR)
    processed_cv = utils.preprocess_for_gemini(cv_img)
    processed_pil = Image.fromarray(cv2.cvtColor(processed_cv, cv2.COLOR_BGR2RGB))

    prompt = """
    Bu görsel bir sınav kağıdının "Öğrenci Bilgileri" kısmıdır.
    
    GÖREV:
    Görseldeki EL YAZISINI oku.
    
    ÇOK ÖNEMLİ KURALLAR (HALLÜSİNASYON ENGELLEME):
    1. SADECE görselde AÇIKÇA görülen yazıları oku.
    2. Eğer bir alan (İsim, Sınıf veya No) BOŞ ise veya sadece matbu yazı (Adı Soyadı vb.) varsa ve el yazısı YOKSA, o alanı BOŞ STRING ("") olarak döndür.
    3. ASLA rastgele isim veya numara uydurma. Emin değilsen "" döndür.
    4. "Adı Soyadı" gibi etiketleri okuma, sadece yanına/altına yazılan DEĞERLERİ oku.
    
    Çıktı Formatı (JSON):
    {
        "name": "Okunan İsim (Yoksa boş)",
        "class_name": "Okunan Sınıf (Yoksa boş)",
        "number": "Okunan Numara (Sadece rakam, yoksa boş)"
    }
    """
    
    try:
        response = gemini_model.generate_content([prompt, processed_pil])
        text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        # Normalize keys just in case
        return {
            "name": data.get("name", "").strip(),
            "class_name": data.get("class_name", "").strip(),
            "number": data.get("number", "").strip()
        }
    except Exception as e:
        print(f"Student Parsing Error: {e}")
        return {"name": "", "class_name": "", "number": ""}
