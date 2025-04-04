import sys
import warnings
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton, 
                           QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QSizePolicy, QStatusBar, QToolBar, QAction, QMessageBox,
                           QDialog, QScrollArea, QGridLayout, QLineEdit, QRadioButton, QButtonGroup, QDialogButtonBox)
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QEvent, QPointF, QByteArray, QBuffer
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QCursor, QIcon, QClipboard, QDoubleValidator, QTransform
import os
import argparse
from PIL import Image, ExifTags
from io import BytesIO
import math

# PyQt5の非推奨警告を抑制
warnings.filterwarnings("ignore", category=DeprecationWarning)

# アイコンのパスを定義
ICONS_DIR = os.path.join(os.path.dirname(__file__), 'icons')

def fix_image_rotation(image_path):
    """EXIF情報に基づいて画像を適切な向きに回転"""
    try:
        image = Image.open(image_path)
        
        # 画像フォーマットを取得（拡張子から）
        format_ext = os.path.splitext(image_path)[1].lower()
        if format_ext.startswith('.'):
            format_ext = format_ext[1:]  # 先頭の'.'を削除
        
        # フォーマットのマッピング
        format_map = {
            'jpg': 'JPEG',
            'jpeg': 'JPEG',
            'png': 'PNG',
            'gif': 'GIF',
            'bmp': 'BMP'
        }
        image_format = format_map.get(format_ext, 'PNG')  # 不明な場合はPNGとして扱う
        
        # EXIF情報を取得
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = dict(image._getexif().items())
            
            if orientation in exif:
                if exif[orientation] == 3:
                    image = image.rotate(180, expand=True)
                elif exif[orientation] == 6:
                    image = image.rotate(270, expand=True)
                elif exif[orientation] == 8:
                    image = image.rotate(90, expand=True)
                
                # 回転した画像をバイト列に変換
                byte_array = BytesIO()
                image.save(byte_array, format=image_format)
                byte_array = byte_array.getvalue()
                
                # QPixmapに変換
                q_image = QImage.fromData(byte_array)
                return QPixmap.fromImage(q_image)
        except (AttributeError, KeyError, IndexError):
            # EXIF情報がない場合は元の画像を返す
            pass
    except Exception as e:
        print(f"画像の回転処理中にエラーが発生しました: {e}")
    
    # エラーが発生した場合や回転が不要な場合は元のQPixmapを返す
    return QPixmap(image_path)

class RotateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("画像を回転")
        self.setModal(True)
        
        # レイアウトの作成
        layout = QVBoxLayout()
        
        # 回転方向の選択
        direction_layout = QHBoxLayout()
        self.direction_group = QButtonGroup(self)
        self.left_radio = QRadioButton("左回り")
        self.right_radio = QRadioButton("右回り")
        self.right_radio.setChecked(True)  # デフォルトは右回り
        self.direction_group.addButton(self.left_radio)
        self.direction_group.addButton(self.right_radio)
        direction_layout.addWidget(self.left_radio)
        direction_layout.addWidget(self.right_radio)
        layout.addLayout(direction_layout)
        
        # 角度入力
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("角度:"))
        self.angle_input = QLineEdit()
        self.angle_input.setValidator(QDoubleValidator(0.0, 360.0, 2))  # 0.0-360.0の範囲で小数点2桁まで
        self.angle_input.setText("90.0")  # デフォルト値
        angle_layout.addWidget(self.angle_input)
        angle_layout.addWidget(QLabel("度"))
        layout.addLayout(angle_layout)
        
        # OKとキャンセルボタン
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_rotation_angle(self):
        """回転角度を取得（正の値が右回り）"""
        try:
            angle = float(self.angle_input.text())
            if self.left_radio.isChecked():
                angle = -angle
            return angle
        except ValueError:
            return 0.0

class ImageLabel(QLabel):
    EDGE_THRESHOLD = 5  # エッジ検出の閾値（ピクセル）
    MIN_SIZE = 1  # 選択範囲の最小サイズ（ピクセル）
    
    class EdgeType:
        NONE = 0
        LEFT = 1
        RIGHT = 2
        TOP = 3
        BOTTOM = 4
        TOP_LEFT = 5
        TOP_RIGHT = 6
        BOTTOM_LEFT = 7
        BOTTOM_RIGHT = 8
        MOVE = 9

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.image_path = None
        self.scale_factor = 1.0
        self.original_pixmap = None
        self.current_pixmap_rect = None
        self.resize_edge = self.EdgeType.NONE
        self.last_cursor = None
        self.last_pos = None
        self.coord_callback = None
        
        # 履歴管理用のスタック
        self.history = []
        self.history_index = -1
        self.max_history = 10  # 履歴の最大数
        
        # 相対座標での選択範囲（0.0 ~ 1.0の範囲）
        self.rel_start_pos = None
        self.rel_end_pos = None
        
        # サイズ変更時の制御用フラグ
        self.is_negative_resize = False
        self.original_edge_pos = None
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        
        self.is_drawing = False
        self.is_resizing = False
        
        # イベントフィルターを設定
        self.window().installEventFilter(self)

    def set_coord_callback(self, callback):
        """座標更新コールバックを設定"""
        self.coord_callback = callback

    def to_relative_pos(self, pos):
        """ローカル座標を相対座標に変換（0.0 ~ 1.0の範囲）"""
        if not self.current_pixmap_rect or not self.original_pixmap:
            return None
        
        # 画像の実際のアスペクト比を計算
        original_aspect = self.original_pixmap.width() / self.original_pixmap.height()
        current_aspect = self.current_pixmap_rect.width() / self.current_pixmap_rect.height()
        
        # 画像の実際の表示領域を計算
        actual_rect = QRect(self.current_pixmap_rect)
        if original_aspect > current_aspect:
            # 横長の画像: 高さを調整
            new_height = int(self.current_pixmap_rect.width() / original_aspect)
            y_offset = (self.current_pixmap_rect.height() - new_height) // 2
            actual_rect.setTop(self.current_pixmap_rect.top() + y_offset)
            actual_rect.setHeight(new_height)
        else:
            # 縦長の画像: 幅を調整
            new_width = int(self.current_pixmap_rect.height() * original_aspect)
            x_offset = (self.current_pixmap_rect.width() - new_width) // 2
            actual_rect.setLeft(self.current_pixmap_rect.left() + x_offset)
            actual_rect.setWidth(new_width)
        
        # 相対座標に変換（制限なし）
        x = (pos.x() - actual_rect.left()) / actual_rect.width()
        y = (pos.y() - actual_rect.top()) / actual_rect.height()
        return QPointF(x, y)

    def to_local_pos(self, rel_pos):
        """相対座標をローカル座標に変換"""
        if not self.current_pixmap_rect or not rel_pos:
            return None
        
        x = self.current_pixmap_rect.left() + (rel_pos.x() * self.current_pixmap_rect.width())
        y = self.current_pixmap_rect.top() + (rel_pos.y() * self.current_pixmap_rect.height())
        return QPoint(int(x), int(y))

    def get_current_rect(self):
        """現在の選択範囲をローカル座標で取得"""
        if not (self.rel_start_pos and self.rel_end_pos and self.current_pixmap_rect):
            return None
        
        # 画像の実際のアスペクト比を計算
        original_aspect = self.original_pixmap.width() / self.original_pixmap.height()
        current_aspect = self.current_pixmap_rect.width() / self.current_pixmap_rect.height()
        
        # 画像の実際の表示領域を計算
        actual_rect = QRect(self.current_pixmap_rect)
        if original_aspect > current_aspect:
            new_height = int(self.current_pixmap_rect.width() / original_aspect)
            y_offset = (self.current_pixmap_rect.height() - new_height) // 2
            actual_rect.setTop(self.current_pixmap_rect.top() + y_offset)
            actual_rect.setHeight(new_height)
        else:
            new_width = int(self.current_pixmap_rect.height() * original_aspect)
            x_offset = (self.current_pixmap_rect.width() - new_width) // 2
            actual_rect.setLeft(self.current_pixmap_rect.left() + x_offset)
            actual_rect.setWidth(new_width)
        
        # 相対座標をローカル座標に変換
        start_x = actual_rect.left() + (self.rel_start_pos.x() * actual_rect.width())
        start_y = actual_rect.top() + (self.rel_start_pos.y() * actual_rect.height())
        end_x = actual_rect.left() + (self.rel_end_pos.x() * actual_rect.width())
        end_y = actual_rect.top() + (self.rel_end_pos.y() * actual_rect.height())
        
        # 選択範囲を作成し、画像の表示領域内に制限
        rect = QRect(QPoint(int(start_x), int(start_y)), QPoint(int(end_x), int(end_y))).normalized()
        return rect.intersected(actual_rect)

    def update_coord_display(self):
        if self.coord_callback:
            if self.rel_start_pos and self.rel_end_pos and self.original_pixmap:
                # 選択範囲の座標を取得
                rect = self.get_selection_rect()
                if rect:
                    # 左上座標を取得
                    image_x = rect.x()
                    image_y = rect.y()
                    size_text = f" | W: {rect.width()}, H: {rect.height()}"
                    self.coord_callback(image_pos=(image_x, image_y), size=size_text)
                else:
                    self.coord_callback()
            else:
                self.coord_callback()

    def clear_selection(self):
        self.rel_start_pos = None
        self.rel_end_pos = None
        self.is_drawing = False
        self.is_resizing = False
        self.resize_edge = self.EdgeType.NONE
        self.last_pos = None
        if hasattr(self, 'coord_callback'):
            self.update_coord_display()

    def eventFilter(self, obj, event):
        if obj == self.window():
            if event.type() == QEvent.Move:
                # ウィンドウ移動時の処理
                if self.rel_start_pos is not None and self.rel_end_pos is not None:
                    # 現在の選択範囲をスクリーン座標に変換
                    old_start_screen = self.get_screen_pos(self.rel_start_pos)
                    old_end_screen = self.get_screen_pos(self.rel_end_pos)
                    
                    # 新しいウィンドウ位置でのローカル座標に変換
                    self.rel_start_pos = self.get_local_pos(old_start_screen)
                    self.rel_end_pos = self.get_local_pos(old_end_screen)
                    
                    self.update()
        return super().eventFilter(obj, event)

    def get_edge_at_position(self, pos):
        if not (self.rel_start_pos and self.rel_end_pos):
            return self.EdgeType.NONE

        rect = self.get_current_rect()
        if not rect:
            return self.EdgeType.NONE

        # 画像の実際の表示領域を計算
        if self.original_pixmap:
            original_aspect = self.original_pixmap.width() / self.original_pixmap.height()
            current_aspect = self.current_pixmap_rect.width() / self.current_pixmap_rect.height()
            
            actual_rect = QRect(self.current_pixmap_rect)
            if original_aspect > current_aspect:
                new_height = int(self.current_pixmap_rect.width() / original_aspect)
                y_offset = (self.current_pixmap_rect.height() - new_height) // 2
                actual_rect.setTop(self.current_pixmap_rect.top() + y_offset)
                actual_rect.setHeight(new_height)
            else:
                new_width = int(self.current_pixmap_rect.height() * original_aspect)
                x_offset = (self.current_pixmap_rect.width() - new_width) // 2
                actual_rect.setLeft(self.current_pixmap_rect.left() + x_offset)
                actual_rect.setWidth(new_width)
            
            # 画像の実際の表示領域外の場合は何も返さない
            if not actual_rect.contains(pos):
                return self.EdgeType.NONE

        x, y = pos.x(), pos.y()
        near_left = abs(x - rect.left()) < self.EDGE_THRESHOLD
        near_right = abs(x - rect.right()) < self.EDGE_THRESHOLD
        near_top = abs(y - rect.top()) < self.EDGE_THRESHOLD
        near_bottom = abs(y - rect.bottom()) < self.EDGE_THRESHOLD

        if rect.contains(pos):
            # コーナーの判定
            if near_top and near_left:
                return self.EdgeType.TOP_LEFT
            elif near_top and near_right:
                return self.EdgeType.TOP_RIGHT
            elif near_bottom and near_left:
                return self.EdgeType.BOTTOM_LEFT
            elif near_bottom and near_right:
                return self.EdgeType.BOTTOM_RIGHT
            # エッジの判定
            elif near_left:
                return self.EdgeType.LEFT
            elif near_right:
                return self.EdgeType.RIGHT
            elif near_top:
                return self.EdgeType.TOP
            elif near_bottom:
                return self.EdgeType.BOTTOM
            return self.EdgeType.MOVE
        return self.EdgeType.NONE

    def update_cursor(self, edge_type):
        if edge_type == self.EdgeType.LEFT or edge_type == self.EdgeType.RIGHT:
            self.setCursor(Qt.SizeHorCursor)
        elif edge_type == self.EdgeType.TOP or edge_type == self.EdgeType.BOTTOM:
            self.setCursor(Qt.SizeVerCursor)
        elif edge_type == self.EdgeType.TOP_LEFT or edge_type == self.EdgeType.BOTTOM_RIGHT:
            self.setCursor(Qt.SizeFDiagCursor)
        elif edge_type == self.EdgeType.TOP_RIGHT or edge_type == self.EdgeType.BOTTOM_LEFT:
            self.setCursor(Qt.SizeBDiagCursor)
        elif edge_type == self.EdgeType.MOVE:
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def get_screen_pos(self, local_pos):
        """ローカル座標をスクリーン座標に変換"""
        return self.mapToGlobal(local_pos)

    def get_local_pos(self, screen_pos):
        """スクリーン座標をローカル座標に変換"""
        return self.mapFromGlobal(screen_pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.pixmap():
            pos = event.pos()
            self.last_pos = pos
            
            # 画像の実際の表示領域を計算
            if self.original_pixmap:
                original_aspect = self.original_pixmap.width() / self.original_pixmap.height()
                current_aspect = self.current_pixmap_rect.width() / self.current_pixmap_rect.height()
                
                actual_rect = QRect(self.current_pixmap_rect)
                if original_aspect > current_aspect:
                    new_height = int(self.current_pixmap_rect.width() / original_aspect)
                    y_offset = (self.current_pixmap_rect.height() - new_height) // 2
                    actual_rect.setTop(self.current_pixmap_rect.top() + y_offset)
                    actual_rect.setHeight(new_height)
                else:
                    new_width = int(self.current_pixmap_rect.height() * original_aspect)
                    x_offset = (self.current_pixmap_rect.width() - new_width) // 2
                    actual_rect.setLeft(self.current_pixmap_rect.left() + x_offset)
                    actual_rect.setWidth(new_width)
            
            edge_type = self.get_edge_at_position(pos)
            if edge_type != self.EdgeType.NONE:
                self.resize_edge = edge_type
                self.is_resizing = True
                self.is_negative_resize = False
                self.original_edge_pos = None
            else:
                # 既存の選択範囲がある場合の処理
                current_rect = self.get_current_rect()
                if current_rect:
                    # 選択範囲内をクリックした場合は移動モード
                    if current_rect.contains(pos):
                        self.resize_edge = self.EdgeType.MOVE
                        self.is_resizing = True
                        return
                    
                    # 選択範囲外をクリックした場合
                    if not current_rect.contains(pos):
                        # 画像の表示領域内でのクリックの場合のみ選択範囲をクリア
                        if actual_rect.contains(pos):
                            self.clear_selection()
                            self.update()
                            # クリック位置から新しい選択範囲の作成を開始
                            rel_pos = self.to_relative_pos(pos)
                            if rel_pos:
                                self.rel_start_pos = rel_pos
                                self.rel_end_pos = rel_pos
                                self.is_drawing = True
                            return
                        else:
                            return
                
                # 新しい選択範囲の作成
                rel_pos = self.to_relative_pos(pos)
                if rel_pos:
                    self.rel_start_pos = rel_pos
                    self.rel_end_pos = rel_pos
                    self.is_drawing = True
            self.update_coord_display()

    def adjust_rect_size(self, rect, edge_type, delta):
        """選択範囲のサイズを調整し、最小サイズを維持"""
        new_rect = QRect(rect)
        adjusted_delta = QPoint(delta.x(), delta.y())
        is_min_size = False
        
        # 画像の実際の表示領域を計算
        if self.original_pixmap:
            original_aspect = self.original_pixmap.width() / self.original_pixmap.height()
            current_aspect = self.current_pixmap_rect.width() / self.current_pixmap_rect.height()
            
            actual_rect = QRect(self.current_pixmap_rect)
            if original_aspect > current_aspect:
                new_height = int(self.current_pixmap_rect.width() / original_aspect)
                y_offset = (self.current_pixmap_rect.height() - new_height) // 2
                actual_rect.setTop(self.current_pixmap_rect.top() + y_offset)
                actual_rect.setHeight(new_height)
            else:
                new_width = int(self.current_pixmap_rect.height() * original_aspect)
                x_offset = (self.current_pixmap_rect.width() - new_width) // 2
                actual_rect.setLeft(self.current_pixmap_rect.left() + x_offset)
                actual_rect.setWidth(new_width)
        
        if edge_type == self.EdgeType.MOVE:
            # 移動時の処理を改善
            new_rect.translate(delta)
            
            # 画像の表示領域内に制限
            if self.original_pixmap:
                # 左端の制限
                if new_rect.left() < actual_rect.left():
                    new_rect.moveLeft(actual_rect.left())
                # 右端の制限
                if new_rect.right() > actual_rect.right():
                    new_rect.moveRight(actual_rect.right())
                # 上端の制限
                if new_rect.top() < actual_rect.top():
                    new_rect.moveTop(actual_rect.top())
                # 下端の制限
                if new_rect.bottom() > actual_rect.bottom():
                    new_rect.moveBottom(actual_rect.bottom())
            
            # 選択範囲が画像の表示領域内に完全に含まれているか確認
            if not actual_rect.contains(new_rect.topLeft()) or not actual_rect.contains(new_rect.bottomRight()):
                return rect, QPoint(0, 0), is_min_size
            
            # 選択範囲が画像の表示領域内に完全に含まれている場合のみ、移動を適用
            if actual_rect.contains(new_rect.topLeft()) and actual_rect.contains(new_rect.bottomRight()):
                return new_rect, adjusted_delta, is_min_size
            else:
                return rect, QPoint(0, 0), is_min_size
        
        return new_rect, adjusted_delta, is_min_size

    def mouseMoveEvent(self, event):
        # グローバル座標を取得
        global_pos = event.globalPos()
        # ウィジェットのローカル座標に変換
        pos = self.mapFromGlobal(global_pos)
        
        if self.is_resizing and self.resize_edge != self.EdgeType.NONE:
            if self.last_pos is not None:
                # 現在の選択範囲を取得
                rect = self.get_current_rect()
                if rect:
                    # グローバル座標での移動量を計算（画面外でも正確な移動量を取得可能）
                    last_global_pos = self.mapToGlobal(self.last_pos)
                    delta = QPoint(
                        global_pos.x() - last_global_pos.x(),
                        global_pos.y() - last_global_pos.y()
                    )
                    
                    # サイズ制限付きで位置を更新し、調整後のdeltaを取得
                    rect, adjusted_delta, is_min_size = self.adjust_rect_size(rect, self.resize_edge, delta)
                    
                    # 最小サイズに達した時の処理
                    if is_min_size:
                        if not self.is_negative_resize:
                            # 初めて最小サイズになった時の位置を記録
                            self.is_negative_resize = True
                            if self.resize_edge in [self.EdgeType.LEFT, self.EdgeType.TOP_LEFT, self.EdgeType.BOTTOM_LEFT]:
                                self.original_edge_pos = rect.left()
                            elif self.resize_edge in [self.EdgeType.RIGHT, self.EdgeType.TOP_RIGHT, self.EdgeType.BOTTOM_RIGHT]:
                                self.original_edge_pos = rect.right()
                            elif self.resize_edge in [self.EdgeType.TOP, self.EdgeType.TOP_LEFT, self.EdgeType.TOP_RIGHT]:
                                self.original_edge_pos = rect.top()
                            elif self.resize_edge in [self.EdgeType.BOTTOM, self.EdgeType.BOTTOM_LEFT, self.EdgeType.BOTTOM_RIGHT]:
                                self.original_edge_pos = rect.bottom()
                    
                    # 負の方向にリサイズ中の処理
                    if self.is_negative_resize:
                        current_pos = None
                        if self.resize_edge in [self.EdgeType.LEFT, self.EdgeType.TOP_LEFT, self.EdgeType.BOTTOM_LEFT]:
                            current_pos = pos.x()
                        elif self.resize_edge in [self.EdgeType.RIGHT, self.EdgeType.TOP_RIGHT, self.EdgeType.BOTTOM_RIGHT]:
                            current_pos = pos.x()
                        elif self.resize_edge in [self.EdgeType.TOP, self.EdgeType.TOP_LEFT, self.EdgeType.TOP_RIGHT]:
                            current_pos = pos.y()
                        elif self.resize_edge in [self.EdgeType.BOTTOM, self.EdgeType.BOTTOM_LEFT, self.EdgeType.BOTTOM_RIGHT]:
                            current_pos = pos.y()
                        
                        # マウスが元の位置を超えて戻ってきた場合、リサイズを再開
                        if current_pos is not None:
                            if ((self.resize_edge in [self.EdgeType.LEFT, self.EdgeType.TOP_LEFT, self.EdgeType.BOTTOM_LEFT] and current_pos <= self.original_edge_pos) or
                                (self.resize_edge in [self.EdgeType.RIGHT, self.EdgeType.TOP_RIGHT, self.EdgeType.BOTTOM_RIGHT] and current_pos >= self.original_edge_pos) or
                                (self.resize_edge in [self.EdgeType.TOP, self.EdgeType.TOP_LEFT, self.EdgeType.TOP_RIGHT] and current_pos <= self.original_edge_pos) or
                                (self.resize_edge in [self.EdgeType.BOTTOM, self.EdgeType.BOTTOM_LEFT, self.EdgeType.BOTTOM_RIGHT] and current_pos >= self.original_edge_pos)):
                                self.is_negative_resize = False
                                self.original_edge_pos = None
                    
                    # 相対座標に変換して保存
                    self.rel_start_pos = self.to_relative_pos(rect.topLeft())
                    self.rel_end_pos = self.to_relative_pos(rect.bottomRight())
                    
                    # 負の方向にリサイズ中でない場合のみ、last_posを更新
                    if not self.is_negative_resize:
                        self.last_pos = QPoint(
                            self.last_pos.x() + adjusted_delta.x(),
                            self.last_pos.y() + adjusted_delta.y()
                        )
                    
            self.update()
            self.update_coord_display()
        elif self.is_drawing:
            # 画像の表示領域内に制限
            if self.current_pixmap_rect:
                pos = QPoint(
                    max(self.current_pixmap_rect.left(), min(pos.x(), self.current_pixmap_rect.right())),
                    max(self.current_pixmap_rect.top(), min(pos.y(), self.current_pixmap_rect.bottom()))
                )
            rel_pos = self.to_relative_pos(pos)
            if rel_pos:
                self.rel_end_pos = rel_pos
                self.update()
                self.update_coord_display()
        else:
            edge_type = self.get_edge_at_position(pos)
            self.update_cursor(edge_type)
        
        self.last_pos = pos

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_drawing = False
            self.is_resizing = False
            self.resize_edge = self.EdgeType.NONE
            self.last_pos = None
            self.is_negative_resize = False
            self.original_edge_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.pixmap():
            pos = event.pos()
            rect = self.get_current_rect()
            if rect:
                parent = self.window()
                if parent and hasattr(parent, 'trim_image'):
                    parent.trim_image()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for file_path in files:
            if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
                self.load_image(file_path)
                # タイトルバーを更新
                parent = self.window()
                if parent:
                    base_name = os.path.basename(file_path)
                    parent.setWindowTitle(f"{base_name} - ImgEZ")
                break

    def load_image(self, image_path):
        """画像を読み込む"""
        self.image_path = image_path
        self.original_pixmap = fix_image_rotation(image_path)
        self.scale_factor = 1.0
        
        # 履歴を空にしてから、現在の画像を最初の履歴として追加
        self.history = []
        self.history.append(self.original_pixmap.copy())
        self.history_index = 0
        
        self.update_scaled_pixmap()
        self.clear_selection()
        self.update()

    def update_scaled_pixmap(self):
        if self.original_pixmap:
            # 余白のサイズを定義
            MARGIN_LEFT = 10
            MARGIN_RIGHT = 10
            MARGIN_TOP = 10
            
            # 余白を考慮したラベルサイズを計算
            label_size = self.size()
            available_width = label_size.width() - (MARGIN_LEFT + MARGIN_RIGHT)
            available_height = label_size.height() - MARGIN_TOP
            
            # 利用可能な領域に合わせて画像をスケーリング
            scaled_pixmap = self.original_pixmap.scaled(
                available_width,
                available_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            original_size = self.original_pixmap.size()
            scaled_size = scaled_pixmap.size()
            self.scale_factor = min(
                scaled_size.width() / original_size.width(),
                scaled_size.height() / original_size.height()
            )
            
            # 画像の表示位置を設定（左右と上部に余白を追加）
            x = MARGIN_LEFT + (available_width - scaled_pixmap.width()) // 2
            y = MARGIN_TOP + (available_height - scaled_pixmap.height()) // 2
            self.current_pixmap_rect = QRect(x, y, scaled_pixmap.width(), scaled_pixmap.height())
            
            # 中央に配置するために空のピクセルマップを作成
            centered_pixmap = QPixmap(label_size)
            centered_pixmap.fill(Qt.transparent)
            
            # 空のピクセルマップに画像を描画
            painter = QPainter(centered_pixmap)
            painter.drawPixmap(x, y, scaled_pixmap)
            painter.end()
            
            self.setPixmap(centered_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.original_pixmap:
            self.update_scaled_pixmap()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rel_start_pos and self.rel_end_pos and self.pixmap():
            rect = self.get_current_rect()
            if rect:
                painter = QPainter(self)
                pen = QPen(QColor(255, 0, 0), 2)
                painter.setPen(pen)
                painter.drawRect(rect)

    def get_selection_rect(self):
        """トリミング用の選択範囲を取得（元画像の座標系で）"""
        if not (self.rel_start_pos and self.rel_end_pos and self.pixmap()):
            return None

        # 元画像での座標を計算
        original_rect = QRect(
            int(self.rel_start_pos.x() * self.original_pixmap.width()),
            int(self.rel_start_pos.y() * self.original_pixmap.height()),
            int((self.rel_end_pos.x() - self.rel_start_pos.x()) * self.original_pixmap.width()),
            int((self.rel_end_pos.y() - self.rel_start_pos.y()) * self.original_pixmap.height())
        ).normalized()

        return original_rect.intersected(self.original_pixmap.rect())

    def copy_to_clipboard(self):
        """画像をクリップボードにコピー"""
        if not self.original_pixmap:
            return False

        clipboard = QApplication.clipboard()
        rect = self.get_selection_rect()
        if rect:
            # 選択範囲がある場合は、その部分だけをコピー
            image = self.original_pixmap.toImage()
            cropped = image.copy(rect)
            clipboard.setImage(cropped)
        else:
            # 選択範囲がない場合は、画像全体をコピー
            clipboard.setPixmap(self.original_pixmap)
        return True

    def add_to_history(self):
        """現在の状態を履歴に追加"""
        if not self.original_pixmap:
            return

        # 現在の状態を保存
        current_state = self.original_pixmap.copy()
        
        # 履歴インデックスより後の履歴を削除
        self.history = self.history[:self.history_index + 1]
        
        # 新しい状態を追加
        self.history.append(current_state)
        self.history_index += 1
        
        # 履歴の最大数を超えた場合、古い履歴を削除
        if len(self.history) > self.max_history:
            self.history.pop(0)
            self.history_index -= 1

    def reset_to_original(self):
        """最初の状態に戻す"""
        if len(self.history) > 0:  # 履歴が存在する場合
            # 最初の履歴を保持
            first_image = self.history[0].copy()
            
            # 履歴を最初の画像のみにする
            self.history = [first_image]
            self.history_index = 0
            
            # 画像を最初の状態に戻す
            self.original_pixmap = first_image
            self.clear_selection()
            self.update_scaled_pixmap()
            return True
        return False

    def undo_last(self):
        """直前の状態に戻す"""
        if len(self.history) > 0:  # 履歴が存在する場合
            # 最後の履歴を表示
            self.original_pixmap = self.history[self.history_index].copy()
            # 最後の履歴を削除
            self.history.pop()
            self.history_index = len(self.history) - 1
            
            self.clear_selection()
            self.update_scaled_pixmap()
            return True
        return False

    def trim_image(self):
        """選択範囲で画像をトリミング"""
        if not self.original_pixmap:
            return

        rect = self.get_selection_rect()
        if not rect:
            return

        # トリミング前の状態を履歴に追加
        self.history.append(self.original_pixmap.copy())
        self.history_index = len(self.history) - 1

        # 選択範囲で画像をトリミング
        image = self.original_pixmap.toImage()
        cropped = image.copy(rect)
        self.original_pixmap = QPixmap.fromImage(cropped)
        
        # 選択範囲をクリアして画像を更新
        self.clear_selection()
        self.update_scaled_pixmap()

    def save_image(self, file_name):
        """画像を保存"""
        if not self.original_pixmap:
            return False
        
        # 現在表示中の画像を保存
        return self.original_pixmap.save(file_name)

    def rotate_image(self, angle):
        """画像を指定された角度だけ回転"""
        if not self.original_pixmap:
            return False
        
        # 回転後の画像全体が表示されるサイズを計算
        rad_angle = math.radians(abs(angle))
        sin_a = abs(math.sin(rad_angle))
        cos_a = abs(math.cos(rad_angle))
        img_width = self.original_pixmap.width()
        img_height = self.original_pixmap.height()
        new_width = int(img_width * cos_a + img_height * sin_a)
        new_height = int(img_width * sin_a + img_height * cos_a)
        
        # 新しいピクセルマップを作成（透明な背景）
        rotated = QPixmap(new_width, new_height)
        rotated.fill(Qt.transparent)
        
        # 回転を実行
        painter = QPainter(rotated)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        # 画像を中央に配置して回転
        transform = QTransform()
        transform.translate(new_width/2, new_height/2)
        transform.rotate(angle)
        transform.translate(-img_width/2, -img_height/2)
        
        painter.setTransform(transform)
        painter.drawPixmap(0, 0, self.original_pixmap)
        painter.end()
        
        # 履歴に追加
        self.history.append(rotated)
        self.history_index = len(self.history) - 1
        
        # 画像を更新
        self.original_pixmap = rotated
        self.clear_selection()
        self.update_scaled_pixmap()
        return True

class HistoryDialog(QDialog):
    """履歴表示用のダイアログ"""
    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("履歴表示")
        self.setMinimumSize(800, 600)
        
        # スクロール可能なエリアを作成
        scroll = QScrollArea(self)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(scroll)
        
        # グリッドレイアウトでサムネイルを配置
        container = QWidget()
        grid = QGridLayout(container)
        
        # 各履歴画像を表示
        for i, pixmap in enumerate(history):
            # サムネイルを作成
            thumb = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label = QLabel()
            label.setPixmap(thumb)
            label.setAlignment(Qt.AlignCenter)
            
            # インデックス表示用のラベル
            index_label = QLabel(f"履歴 {i}")
            index_label.setAlignment(Qt.AlignCenter)
            
            # 垂直レイアウトでサムネイルとインデックスを配置
            thumb_container = QWidget()
            v_layout = QVBoxLayout(thumb_container)
            v_layout.addWidget(label)
            v_layout.addWidget(index_label)
            
            # グリッドに配置（4列で配置）
            row = i // 4
            col = i % 4
            grid.addWidget(thumb_container, row, col)
        
        container.setLayout(grid)
        scroll.setWidget(container)
        scroll.setWidgetResizable(True)

class MainWindow(QMainWindow):
    def __init__(self, debug_mode=False):
        super().__init__()
        self.setWindowTitle("ImgEZ")
        self.setMinimumSize(800, 600)
        
        # デバッグモードの設定
        self.debug_mode = debug_mode

        # ショートカットキーの設定（最初に実行）
        self.setup_shortcuts()
        
        # メニューバーの作成
        self.create_menu_bar()
        
        # ツールバーの作成
        self.create_tool_bar()
        
        # 中央ウィジェットの設定
        self.image_label = ImageLabel()
        self.setCentralWidget(self.image_label)
        
        # ステータスバーの作成
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.coord_label = QLabel()
        self.statusBar.addPermanentWidget(self.coord_label)
        
        # 画像ラベルのコールバック設定
        self.image_label.coord_callback = self.update_coord_display

    def setup_shortcuts(self):
        """ショートカットキーの設定"""
        # コピー (Ctrl+C)
        self.copy_action = QAction("コピー", self)
        self.copy_action.setShortcut("Ctrl+C")
        self.copy_action.triggered.connect(self.copy_image)
        copy_icon_path = os.path.join(ICONS_DIR, 'copy.svg')
        if os.path.exists(copy_icon_path):
            self.copy_action.setIcon(QIcon(copy_icon_path))
        else:
            self.copy_action.setIcon(self.style().standardIcon(self.style().SP_FileDialogDetailedView))
        
        # 直前に戻す (Ctrl+Z)
        self.undo_action = QAction("直前に戻す", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.undo_last_image)
        undo_icon_path = os.path.join(ICONS_DIR, 'undo.svg')
        if os.path.exists(undo_icon_path):
            self.undo_action.setIcon(QIcon(undo_icon_path))
        else:
            self.undo_action.setIcon(self.style().standardIcon(self.style().SP_ArrowBack))
        
        # 回転 (Ctrl+R)
        self.rotate_action = QAction("回転", self)
        self.rotate_action.setShortcut("Ctrl+R")
        self.rotate_action.triggered.connect(self.rotate_image)
        rotate_icon_path = os.path.join(ICONS_DIR, 'rotate.svg')
        if os.path.exists(rotate_icon_path):
            self.rotate_action.setIcon(QIcon(rotate_icon_path))
        else:
            # SP_BrowserReloadを使用（時計回りの矢印アイコン）
            self.rotate_action.setIcon(self.style().standardIcon(self.style().SP_BrowserReload))
        
        # 最初に戻す (Ctrl+Alt+R)
        self.reset_action = QAction("最初に戻す", self)
        self.reset_action.setShortcut("Ctrl+Alt+R")
        self.reset_action.triggered.connect(self.reset_to_original)
        reset_icon_path = os.path.join(ICONS_DIR, 'reset.svg')
        if os.path.exists(reset_icon_path):
            self.reset_action.setIcon(QIcon(reset_icon_path))
        else:
            # フォールバックアイコンとしてSP_DialogApplyButtonを使用
            self.reset_action.setIcon(self.style().standardIcon(self.style().SP_DialogApplyButton))
        
        # トリミング (Ctrl+T)
        self.trim_action = QAction("トリミング", self)
        self.trim_action.setShortcut("Ctrl+T")
        self.trim_action.triggered.connect(self.trim_image)
        trim_icon_path = os.path.join(ICONS_DIR, 'trim.svg')
        if os.path.exists(trim_icon_path):
            self.trim_action.setIcon(QIcon(trim_icon_path))
        else:
            self.trim_action.setIcon(self.style().standardIcon(self.style().SP_TitleBarMaxButton))
        
        # 選択解除 (Esc)
        self.clear_action = QAction("選択解除", self)
        self.clear_action.setShortcut("Esc")
        self.clear_action.triggered.connect(self.clear_selection)
        clear_icon_path = os.path.join(ICONS_DIR, 'clear.svg')
        if os.path.exists(clear_icon_path):
            self.clear_action.setIcon(QIcon(clear_icon_path))
        else:
            self.clear_action.setIcon(self.style().standardIcon(self.style().SP_DialogCancelButton))
        
        # 開く (Ctrl+O)
        self.open_action = QAction("開く", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_image)
        self.open_action.setIcon(self.style().standardIcon(self.style().SP_DialogOpenButton))
        
        # 保存 (Ctrl+S)
        self.save_action = QAction("保存", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_image)
        self.save_action.setIcon(self.style().standardIcon(self.style().SP_DialogSaveButton))
        
        # 終了 (Ctrl+Q)
        self.exit_action = QAction("終了", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(self.close)
        self.exit_action.setIcon(self.style().standardIcon(self.style().SP_DialogCloseButton))
        
        # 履歴表示（デバッグ用）
        self.history_action = QAction("履歴表示", self)
        self.history_action.triggered.connect(self.show_history)
        self.history_action.setIcon(self.style().standardIcon(self.style().SP_FileDialogInfoView))

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menubar.addMenu("ファイル")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)
        
        # 編集メニュー
        edit_menu = menubar.addMenu("編集")
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.reset_action)
        edit_menu.addAction(self.rotate_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.trim_action)
        edit_menu.addAction(self.clear_action)

    def create_tool_bar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # アイコンのみ表示に設定
        toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        
        # ファイル操作
        self.open_action.setToolTip("開く")
        toolbar.addAction(self.open_action)
        
        self.save_action.setToolTip("保存")
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        
        # 編集操作
        self.copy_action.setToolTip("コピー")
        toolbar.addAction(self.copy_action)
        
        self.undo_action.setToolTip("直前に戻す")
        toolbar.addAction(self.undo_action)
        
        self.reset_action.setToolTip("最初に戻す")
        toolbar.addAction(self.reset_action)
        toolbar.addSeparator()
        
        # 回転操作
        self.rotate_action.setToolTip("回転")
        toolbar.addAction(self.rotate_action)
        
        # トリミング操作
        self.trim_action.setToolTip("トリミング")
        toolbar.addAction(self.trim_action)
        
        self.clear_action.setToolTip("選択解除")
        toolbar.addAction(self.clear_action)
        
        # デバッグモードの場合のみ履歴表示ボタンを追加
        if self.debug_mode:
            toolbar.addSeparator()
            self.history_action.setToolTip("履歴表示")
            toolbar.addAction(self.history_action)

    def update_coord_display(self, image_pos=None, size=""):
        if image_pos:
            coord_text = f"XY: ({image_pos[0]}, {image_pos[1]}){size}"
            self.coord_label.setText(coord_text)
        else:
            self.coord_label.clear()

    def open_image(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "画像を開く",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*.*)"
        )
        if file_name:
            self.image_label.load_image(file_name)
            # タイトルバーを更新
            base_name = os.path.basename(file_name)
            self.setWindowTitle(f"{base_name} - ImgEZ")

    def save_image(self):
        if not self.image_label.pixmap():
            QMessageBox.warning(self, "警告", "保存する画像がありません。")
            return
        
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "名前を付けて保存",
            "",
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;All Files (*.*)"
        )
        if file_name:
            if self.image_label.save_image(file_name):
                self.statusBar.showMessage("画像を保存しました", 2000)
            else:
                self.statusBar.showMessage("画像の保存に失敗しました", 2000)

    def trim_image(self):
        if not self.image_label.pixmap():
            QMessageBox.warning(self, "警告", "トリミングする画像がありません。")
            return
            
        if not self.image_label.get_current_rect():
            QMessageBox.warning(self, "警告", "トリミング範囲が選択されていません。")
            return
            
        self.image_label.trim_image()

    def clear_selection(self):
        if self.image_label.pixmap():
            self.image_label.clear_selection()
            self.image_label.update()

    def copy_image(self):
        """画像をクリップボードにコピー"""
        if not self.image_label.pixmap():
            QMessageBox.warning(self, "警告", "コピーする画像がありません。")
            return
        
        if self.image_label.copy_to_clipboard():
            self.statusBar.showMessage("画像をクリップボードにコピーしました", 2000)

    def undo_last_image(self):
        """直前の状態に戻す"""
        if not self.image_label.pixmap():
            QMessageBox.warning(self, "警告", "画像がありません。")
            return
        
        if self.image_label.undo_last():
            self.statusBar.showMessage("直前の状態に戻しました", 2000)
        else:
            self.statusBar.showMessage("これ以上戻せません", 2000)

    def reset_to_original(self):
        """最初の状態に戻す"""
        if not self.image_label.pixmap():
            QMessageBox.warning(self, "警告", "画像がありません。")
            return
        
        if self.image_label.reset_to_original():
            self.statusBar.showMessage("最初の状態に戻しました", 2000)
            # タイトルバーを元に戻す
            self.setWindowTitle("ImgEZ")
        else:
            self.statusBar.showMessage("これ以上戻せません", 2000)

    def show_history(self):
        """履歴表示ダイアログを表示（デバッグ用）"""
        if not self.image_label.pixmap():
            QMessageBox.warning(self, "警告", "画像がありません。")
            return
        
        dialog = HistoryDialog(self.image_label.history, self)
        dialog.exec_()

    def rotate_image(self):
        """画像を回転"""
        if not self.image_label.pixmap():
            QMessageBox.warning(self, "警告", "回転する画像がありません。")
            return
        
        dialog = RotateDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            angle = dialog.get_rotation_angle()
            if self.image_label.rotate_image(angle):
                self.statusBar.showMessage(f"画像を{abs(angle)}度{'左' if angle < 0 else '右'}に回転しました", 2000)
            else:
                self.statusBar.showMessage("画像の回転に失敗しました", 2000)

def main():
    # コマンドライン引数のパース
    parser = argparse.ArgumentParser(description='ImgEZ - 画像トリミングツール')
    parser.add_argument('-D', '--debug', action='store_true', help='デバッグモードで実行')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = MainWindow(debug_mode=args.debug)
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main() 