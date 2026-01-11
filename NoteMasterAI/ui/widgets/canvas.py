
import uuid
import numpy as np
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsItem, QGraphicsPathItem
from PyQt5.QtCore import Qt, QRectF, pyqtSignal
from PyQt5.QtGui import QPixmap, QPen, QColor, QBrush, QPainter, QPainterPath, QImage

from logic.constants import YOLO_CLASS_MAPPING
from logic.utils import pil_to_qpixmap # or cv2_to_qpixmap depending on usage

class ResizeHandle(QGraphicsRectItem):
    def __init__(self, cursor, parent):
        super().__init__(0, 0, 8, 8, parent)
        self.setCursor(cursor)
        self.setBrush(QBrush(QColor("white")))
        self.setPen(QPen(QColor("black"), 1))
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

class ResizableRectItem(QGraphicsRectItem):
    def __init__(self, x, y, w, h, zone_data, parent_scene):
        super().__init__(x, y, w, h)
        self.setFlags(
            QGraphicsItem.ItemIsSelectable | 
            QGraphicsItem.ItemIsMovable | 
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.zone_data = zone_data
        self.parent_scene = parent_scene
        
        self.handle_size = 8
        self.current_handle = None
        self.update_style()

    def boundingRect(self):
        rect = self.rect()
        s = self.handle_size
        return rect.adjusted(-s, -s, s, s)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        
        # 1. Selection Handles
        if self.isSelected() and not self.locked:
            rect = self.rect()
            painter.setBrush(QBrush(QColor("white")))
            painter.setPen(QPen(QColor("black"), 1))
            
            s = self.handle_size
            offset = s/2
            tl, tr = rect.topLeft(), rect.topRight()
            bl, br = rect.bottomLeft(), rect.bottomRight()
            
            for pt in [tl, tr, bl, br]:
                painter.drawRect(QRectF(pt.x() - offset, pt.y() - offset, s, s))
                
        # 2. Answer Text (If present)
        ans = self.zone_data.get("answer")
        if ans:
             rect = self.rect()
             font = painter.font()
             font.setBold(True)
             # User requested "half of classic size" and "all same". 
             # Classic was rect.height()*0.3. A typical line height is ~20-30px, so 10-12px is reasonable fixed size.
             # UPDATE: User requested +75% larger. 12 * 1.75 = 21. Let's use 20.
             font.setPixelSize(20) 
             painter.setFont(font)
             painter.setPen(QPen(Qt.black))
             # Wrap text
             painter.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, str(ans))

    def update_style(self):
        mapped = None
        current_type = self.zone_data.get("zone_type")
        for k, v in YOLO_CLASS_MAPPING.items():
            if v["type"] == current_type:
                mapped = v
                break
        
        if not mapped: mapped = YOLO_CLASS_MAPPING[0]
        c = mapped["color"]
        self.setBrush(QBrush(QColor(c[0], c[1], c[2], c[3])))
        self.setPen(QPen(QColor(c[0], c[1], c[2], 255), 2))
        
        # Locked visual cue? Maybe different border style?
        # Keeping it subtle for now.

    # --- Interaction Logic ---
    
    locked = False
    
    def set_locked(self, locked):
        self.locked = locked
        self.setFlag(QGraphicsItem.ItemIsMovable, not locked)
        # Selectable remains True (we need to select to type answer)
    
    def hoverMoveEvent(self, event):
        if self.locked:
            self.setCursor(Qt.PointingHandCursor)
            return

        pos = event.pos()
        rect = self.rect()
        s = self.handle_size
        offset = s
        
        if not self.isSelected():
            self.setCursor(Qt.OpenHandCursor)
            return

        tl = (pos - rect.topLeft()).manhattanLength() < offset
        tr = (pos - rect.topRight()).manhattanLength() < offset
        bl = (pos - rect.bottomLeft()).manhattanLength() < offset
        br = (pos - rect.bottomRight()).manhattanLength() < offset
        
        if tl or br: self.setCursor(Qt.SizeFDiagCursor)
        elif tr or bl: self.setCursor(Qt.SizeBDiagCursor)
        else: self.setCursor(Qt.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self.locked:
            # Just select, no handles
            super().mousePressEvent(event)
            return
            
        if self.isSelected() and event.button() == Qt.LeftButton:
            pos = event.pos()
            rect = self.rect()
            offset = self.handle_size
            
            if (pos - rect.topLeft()).manhattanLength() < offset: self.current_handle = "tl"
            elif (pos - rect.topRight()).manhattanLength() < offset: self.current_handle = "tr"
            elif (pos - rect.bottomLeft()).manhattanLength() < offset: self.current_handle = "bl"
            elif (pos - rect.bottomRight()).manhattanLength() < offset: self.current_handle = "br"
            else: self.current_handle = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.locked: return 

        if self.current_handle:
            pos = event.pos()
            rect = self.rect()
            if self.current_handle == "tl": rect.setTopLeft(pos)
            elif self.current_handle == "tr": rect.setTopRight(pos)
            elif self.current_handle == "bl": rect.setBottomLeft(pos)
            elif self.current_handle == "br": rect.setBottomRight(pos)
            
            self.setRect(rect.normalized())
            self.update_geometry_data()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.current_handle = None
        super().mouseReleaseEvent(event)
        self.update_geometry_data()
        if self.parent_scene:
            self.parent_scene.item_selected.emit(self)

    def update_geometry_data(self):
        rect = self.rect()
        pos = self.pos() # The item's local origin relative to scene
        # Actually in QGraphicsRectItem, the rect is local coords and pos is the offset.
        # But we are modifying the local rect directly in mouseMoveEvent.
        # So "scene position" = pos() + rect().topLeft() roughly.
        
        # Let's trust logic: 
        final_x = pos.x() + rect.x()
        final_y = pos.y() + rect.y()
        
        self.zone_data["left"] = final_x
        self.zone_data["top"] = final_y
        self.zone_data["width"] = rect.width()
        self.zone_data["height"] = rect.height()


class CanvasWidget(QGraphicsView): # Renamed to match old class name but using new logic
    item_selected = pyqtSignal(object)
    zone_selected = pyqtSignal(object) # Alias for item_selected for compatibility
    zone_added = pyqtSignal(dict) # Keep compatibility signals if needed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self) # Logic uses 'scene'
        self.setScene(self._scene)
        self._scene.item_selected = self.item_selected # Monkey patch signal passthrough
        self.item_selected.connect(self.zone_selected) # Forward signal
        
        self.mode = "transform"
        self.start_point = None
        self.current_drawing_item = None
        self.pixmap_item = None
        
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setBackgroundBrush(QBrush(QColor("#2d2d30")))

    def set_image(self, pil_image):
        self._scene.clear()
        if pil_image:
             pixmap = pil_to_qpixmap(pil_image)
             self.pixmap_item = self._scene.addPixmap(pixmap)
             self._scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
             self.zoom_to_fit()

    def load_zones(self, zones):
        # Clear existing rects
        for item in self._scene.items():
            if isinstance(item, ResizableRectItem):
                self._scene.removeItem(item)
                
        for z in zones:
            item = ResizableRectItem(z["left"], z["top"], z["width"], z["height"], z, self._scene)
            self._scene.addItem(item)

    def set_tool(self, mode):
        self.mode = mode
        if mode == "rect":
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)
        elif mode == "pen":
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.ArrowCursor) # Or a pen cursor
        elif mode == "eraser":
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.PointingHandCursor) # Or eraser cursor
        else:
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.setCursor(Qt.ArrowCursor)

    # Proxy events to Scene logic or handle here
    
    def set_pen_color(self, color):
        self.pen_color = color
        
    current_path_item = None
    
    def mousePressEvent(self, event):
        if self.mode == "pen" and event.button() == Qt.LeftButton:
            self.current_path_item = QGraphicsPathItem()
            pen = QPen(Qt.black, 4) # Black pen, thicker (4)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            self.current_path_item.setPen(pen)
            self._scene.addItem(self.current_path_item)
            
            path = QPainterPath(self.mapToScene(event.pos()))
            self.current_path_item.setPath(path)
            return

        if self.mode == "eraser" and event.button() == Qt.LeftButton:
            items = self._scene.items(self.mapToScene(event.pos()))
            for item in items:
                if isinstance(item, QGraphicsPathItem):
                    self._scene.removeItem(item)
            return
            
        # We need to intersect events before GraphicsView handles drags
        if self.mode == "rect" and event.button() == Qt.LeftButton:
            sp = self.mapToScene(event.pos())
            self.start_point = sp
            self.current_drawing_item = QGraphicsRectItem()
            self.current_drawing_item.setPen(QPen(Qt.green, 2, Qt.DashLine))
            self._scene.addItem(self.current_drawing_item)
            return # Don't propogate
            
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.mode == "pen" and self.current_path_item:
            path = self.current_path_item.path()
            path.lineTo(self.mapToScene(event.pos()))
            self.current_path_item.setPath(path)
            return

        if self.mode == "eraser" and event.buttons() & Qt.LeftButton:
            # Drag to erase
            items = self._scene.items(self.mapToScene(event.pos()))
            for item in items:
                if isinstance(item, QGraphicsPathItem):
                    self._scene.removeItem(item)
            return
            
        if self.mode == "rect" and self.current_drawing_item:
            cp = self.mapToScene(event.pos())
            x = min(self.start_point.x(), cp.x())
            y = min(self.start_point.y(), cp.y())
            w = abs(self.start_point.x() - cp.x())
            h = abs(self.start_point.y() - cp.y())
            self.current_drawing_item.setRect(x, y, w, h)
            return
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.mode == "pen":
            self.current_path_item = None
            return
            
        if self.mode == "rect" and self.current_drawing_item:
            self._scene.removeItem(self.current_drawing_item)
            rect = self.current_drawing_item.rect()
            
            if rect.width() > 5 and rect.height() > 5:
                zone_data = {
                    "id": str(uuid.uuid4()),
                    "zone_name": "Yeni Soru",
                    "zone_type": "Tanımsız",
                    "zone_points": 5.0,
                    "num_options": 5,
                    "left": rect.x(), "top": rect.y(), 
                    "width": rect.width(), "height": rect.height()
                }
                
                real_item = ResizableRectItem(rect.x(), rect.y(), rect.width(), rect.height(), zone_data, self._scene)
                self._scene.addItem(real_item)
                self.item_selected.emit(real_item)
                self.zone_added.emit(zone_data)
            
            self.current_drawing_item = None
            self.set_tool("transform")
            return
            
        super().mouseReleaseEvent(event)

    def render_canvas(self):
        # 1. Hide Zones
        zone_items = []
        for item in self._scene.items():
            if isinstance(item, ResizableRectItem):
                if item.isVisible():
                    item.setVisible(False)
                    zone_items.append(item)
        
        # 2. Render
        rect = self._scene.sceneRect()
        image = QImage(int(rect.width()), int(rect.height()), QImage.Format_RGB32)
        image.fill(Qt.white)
        
        painter = QPainter(image)
        self._scene.render(painter)
        painter.end()
        
        # 3. Restore Zones
        for item in zone_items:
            item.setVisible(True)
            
        # Convert QImage to PIL
        image = image.convertToFormat(QImage.Format_RGBA8888)
        width = image.width()
        height = image.height()
        ptr = image.bits()
        ptr.setsize(height * width * 4)
        from PIL import Image
        arr = np.array(ptr).reshape(height, width, 4)
        return Image.fromarray(arr, "RGBA").convert("RGB")

    def zoom_in(self):
        self.scale(1.2, 1.2)

    def zoom_out(self):
        self.scale(1/1.2, 1/1.2)

    def zoom_to_fit(self):
        if self._scene.itemsBoundingRect().width() > 0:
            self.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)

