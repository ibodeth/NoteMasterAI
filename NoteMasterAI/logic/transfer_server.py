import http.server
import socket
import threading
import json
import base64
import os
import cv2
import numpy as np
import shutil
import cgi
from logic import pdf_utils
from logic.alignment import align_image
from PyQt5.QtCore import QObject, pyqtSignal

# Global reference for the server to access
CURRENT_REFERENCE_IMAGE = None
SESSION_PDF_IMAGES = {} # 1-based index: cv2 image
UPLOAD_DIR = "d:/Projects/NoteMaster/Scans"

def set_reference_image(img):
    global CURRENT_REFERENCE_IMAGE
    # Check if PIL Image
    if hasattr(img, 'save'): 
        # Convert PIL to OpenCV (RGB -> BGR)
        img_np = np.array(img.convert('RGB'))
        CURRENT_REFERENCE_IMAGE = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    else:
        CURRENT_REFERENCE_IMAGE = img

class ServerSignals(QObject):
    log = pyqtSignal(str)
    status_update = pyqtSignal(str)
    finished = pyqtSignal()
    image_received = pyqtSignal(object, str)

class MobileRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/verify':
            self.handle_verify()
        elif self.path == '/save':
            self.handle_save()
        elif self.path == '/set_pdf':
            self.handle_set_pdf()
        else:
            self.send_error(404)

    def handle_set_pdf(self):
        try:
            content_type = self.headers.get('content-type')
            if not content_type: return
            ctype, pdict = cgi.parse_header(content_type)
            pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
            fields = cgi.parse_multipart(self.rfile, pdict)
            
            if 'pdf' in fields:
                pdf_bytes = fields['pdf'][0]
                try:
                    images = pdf_utils.pdf_to_images(pdf_bytes)
                    
                    global SESSION_PDF_IMAGES
                    SESSION_PDF_IMAGES.clear()
                    
                    for i, pil_img in enumerate(images):
                        # Convert PIL RGB to CV2 BGR
                        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                        SESSION_PDF_IMAGES[i+1] = cv_img
                        
                    print(f"DEBUG: Session PDF Loaded. {len(images)} pages.")
                    if hasattr(self.server, 'signals'):
                        self.server.signals.log.emit(f"Mobil PDF Yüklendi: {len(images)} sayfa")
                        
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"OK")
                except Exception as e:
                    print(f"PDF Process Error: {e}")
                    self.send_error(500, str(e))
            else:
                self.send_error(400, "No PDF field")
        except Exception as e:
            print(f"Set PDF Error: {e}")
            self.send_error(500)

    def handle_verify(self):
        try:
            # Parse Header
            content_type = self.headers.get('content-type')
            if not content_type:
                self.send_error(400, "No content-type")
                return
                
            ctype, pdict = cgi.parse_header(content_type)
            if ctype != 'multipart/form-data':
                self.send_error(400, "Expect multipart/form-data")
                return

            pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
            # cgi.parse_multipart is deprecated but effectively standard for simple use. 
            fields = cgi.parse_multipart(self.rfile, pdict)
            
            if 'image' not in fields:
                 self.send_error(400, "No image field")
                 return

            # parse_multipart returns list of bytes
            file_data = fields['image'][0]
            nparr = np.frombuffer(file_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Safe Parsing
            val = fields.get('page_num', [b'1'])[0]
            if isinstance(val, bytes):
                page_num_str = val.decode('utf-8')
            else:
                page_num_str = str(val)

            try:
                page_num = int(page_num_str)
            except: 
                page_num = 1
                
            # Get Reference from Session if available
            ref_img = SESSION_PDF_IMAGES.get(page_num)
            
            # Fallback to Global Single Ref
            if ref_img is None:
                ref_img = CURRENT_REFERENCE_IMAGE
            
            status = "raw"
            preview_b64 = ""
            aligned = None
            
            # Perform Alignment
            if ref_img is not None:
                try:
                    aligned = align_image(ref_img, img)
                    if aligned is not None:
                        status = "aligned"
                        # Resize for preview (max 500px)
                        h, w = aligned.shape[:2]
                        scale = 500 / max(h, w)
                        small = cv2.resize(aligned, None, fx=scale, fy=scale)
                        _, buf = cv2.imencode('.jpg', small)
                        preview_b64 = base64.b64encode(buf).decode('utf-8')
                    else:
                        status = "failed"
                except Exception as e:
                    print(f"Alignment Internal Error: {e}")
                    status = "failed"
            else:
                status = "no_ref"
            
            # Signal UI
            if hasattr(self.server, 'signals'):
                 # Send aligned if available, else raw
                 display_img = aligned if status == "aligned" else img
                 self.server.signals.image_received.emit(display_img, status)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"status": status, "preview": preview_b64}).encode('utf-8'))
                
        except Exception as e:
            print(f"Verify Error: {e}")
            self.send_response(500)
            self.end_headers()

    def handle_save(self):
        try:
            content_type = self.headers.get('content-type')
            if not content_type: return
            ctype, pdict = cgi.parse_header(content_type)
            pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
            fields = cgi.parse_multipart(self.rfile, pdict)
            
            file_data = fields.get('image', [None])[0]
            
            def get_text(k):
                val = fields.get(k, [None])[0]
                if val is None: return "Unknown"
                if isinstance(val, bytes): return val.decode('utf-8')
                return str(val)

            pdf_name = get_text('pdf_name')
            student_name = get_text('student_name')
            page_num = get_text('page_num')

            if file_data:
                # Use Global UPLOAD_DIR (can be modified by GradingTab)
                # User requested flattened structure: BaseFolder/StudentName/Image.jpg
                save_path = os.path.join(UPLOAD_DIR, student_name)
                os.makedirs(save_path, exist_ok=True)
                
                file_path = os.path.join(save_path, f"{student_name}_p{page_num}.jpg")
                
                # 1. Save RAW Image (No Processing)
                with open(file_path, 'wb') as f:
                    f.write(file_data)
                
                # 2. Save Reference (if provided) - For debugging/comparison
                if 'reference' in fields:
                    try:
                         ref_data = fields['reference'][0]
                         ref_path = os.path.join(save_path, f"{student_name}_p{page_num}_ref.png")
                         with open(ref_path, 'wb') as f:
                             f.write(ref_data)
                    except Exception as e:
                         print(f"Ref Save Error: {e}")

                # Debug Resolution check to inform user
                nparr = np.frombuffer(file_data, np.uint8)
                img_check = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img_check is not None:
                    h, w = img_check.shape[:2]
                    res_info = f"({w}x{h}px)"
                else:
                    res_info = "(Boyut?)"

                # Signal Logging if possible
                if hasattr(self.server, 'signals'):
                     self.server.signals.log.emit(f"Mobil Kayıt: {student_name} - Sayfa {page_num} {res_info}")
                
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_error(400, "Missing file")
        except Exception as e:
            print(f"Save Error: {e}")
            self.send_error(500)
            
    def log_message(self, format, *args):
        return # Silence console logs

class TransferServer:
    def __init__(self, port=5000):
        self.port = port
        self.server = None
        self.thread = None
        self.signals = ServerSignals()
        self.running = False
        self.udp_running = False
        self.udp_thread = None

    def start(self):
        if self.running: return
        self.running = True
        
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        
        self.udp_running = True
        self.udp_thread = threading.Thread(target=self._udp_listen)
        self.udp_thread.daemon = True
        self.udp_thread.start()
        
        self.signals.log.emit(f"Sunucu Başlatıldı: {self.get_ip()}:{self.port}")
        self.signals.status_update.emit("Hazır")

    def _udp_listen(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', 5005))
            while self.udp_running:
                data, addr = sock.recvfrom(1024)
                print(f"DEBUG: UDP Packet from {addr}: {data}")
                if data == b"DISCOVER_NOTE_MASTER":
                    sock.sendto(b"NOTE_MASTER_HERE", addr)
        except Exception as e:
            print(f"UDP Error: {e}")

    def _run(self):
        try:
            self.server = http.server.HTTPServer(('0.0.0.0', self.port), MobileRequestHandler)
            self.server.signals = self.signals 
            self.server.serve_forever()
        except Exception as e:
            self.signals.log.emit(f"Sunucu Hatası: {e}")

    def stop(self):
        self.running = False
        self.udp_running = False
        
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        
        # UDP socket doesn't close easily from other thread without sending a packet or timeout, 
        # but daemon thread will die with app.
        
        self.signals.log.emit("Sunucu Durduruldu.")

    def get_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
