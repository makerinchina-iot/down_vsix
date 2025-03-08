import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QListWidget, QLabel, QMessageBox, QStyledItemDelegate, QListWidgetItem, QStyle
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QRect
from PyQt5.QtGui import QFont, QColor, QPainter, QFontMetrics
import requests
import json
import os
import qtmodern.styles
import qtmodern.windows

class ExtensionItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # 如果项目被选中，绘制选中背景
        if option.state & QStyle.State_Selected:
            # 使用更符合黑色主题的选中背景色
            painter.fillRect(option.rect, QColor(51, 153, 255, 80))  # 蓝色带透明度
        else:
            # 为非选中项设置背景色
            painter.fillRect(option.rect, QColor(37, 37, 38))
        
        # 获取数据
        extension = index.data(Qt.UserRole)
        if not extension:
            return super().paint(painter, option, index)
        
        # 设置字体和颜色
        title_font = QFont("Arial", 10, QFont.Bold)
        normal_font = QFont("Arial", 9)
        desc_font = QFont("Arial", 8)
        
        # 修改文字颜色以适应黑色主题
        title_color = QColor(78, 203, 255) if option.state & QStyle.State_Selected else QColor(78, 203, 255)
        normal_color = QColor(230, 230, 230)
        desc_color = QColor(180, 180, 180)
        
        # 绘制区域
        rect = option.rect
        padding = 10
        
        # 绘制标题
        painter.setFont(title_font)
        painter.setPen(title_color)
        title_rect = QRect(rect.left() + padding, rect.top() + padding, rect.width() - 2 * padding, 20)
        display_name = extension.get('displayName', 'Unknown')
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignTop, display_name)
        
        # 绘制发布者
        painter.setFont(normal_font)
        painter.setPen(normal_color)
        publisher_rect = QRect(rect.left() + padding, rect.top() + padding + 20, rect.width() - 2 * padding, 20)
        publisher = extension.get('publisher', {}).get('displayName', 'Unknown')
        painter.drawText(publisher_rect, Qt.AlignLeft | Qt.AlignTop, publisher)
        
        # 绘制下载量
        download_count = "未知"
        for stat in extension.get('statistics', []):
            if stat.get('statisticName') == 'install':
                download_count = f"{int(stat.get('value', 0)):,}"
                break
        
        download_rect = QRect(rect.left() + padding, rect.top() + padding + 40, rect.width() - 2 * padding, 20)
        painter.setPen(desc_color)
        painter.drawText(download_rect, Qt.AlignLeft | Qt.AlignTop, f"下载量: {download_count}")
        
        # 绘制描述
        painter.setFont(desc_font)
        desc_rect = QRect(rect.left() + padding, rect.top() + padding + 60, rect.width() - 2 * padding, 20)
        short_description = extension.get('shortDescription', '无描述')
        # 限制描述长度
        fm = QFontMetrics(desc_font)
        short_description = fm.elidedText(short_description, Qt.ElideRight, rect.width() - 2 * padding)
        painter.drawText(desc_rect, Qt.AlignLeft | Qt.AlignTop, short_description)
    
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 100)  # 每个项目的高度

class VSCodeExtensionDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('VSCode插件下载器')
        self.setGeometry(100, 100, 800, 600)
        self.initUI()

    def initUI(self):
        # 创建中央部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 搜索区域
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('输入插件名称搜索...')
        self.search_button = QPushButton('搜索')
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        layout.addLayout(search_layout)

        # 结果列表
        self.result_list = QListWidget()
        self.result_list.setItemDelegate(ExtensionItemDelegate())  # 设置自定义委托
        self.result_list.setSpacing(5)  # 设置项目间距
        layout.addWidget(self.result_list)

        # 下载按钮
        self.download_button = QPushButton('下载选中的插件')
        layout.addWidget(self.download_button)

        # 状态栏
        self.statusBar().showMessage('就绪')

        # 连接信号和槽
        self.search_button.clicked.connect(self.search_extensions)
        self.download_button.clicked.connect(self.download_extension)
        self.search_input.returnPressed.connect(self.search_extensions)

        # 初始化搜索和下载线程
        self.search_thread = None
        self.download_thread = None

    def search_extensions(self):
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, '警告', '请输入搜索关键词')
            return

        self.statusBar().showMessage('正在搜索...')
        self.search_button.setEnabled(False)
        self.result_list.clear()

        self.search_thread = SearchThread(query)
        self.search_thread.finished.connect(self.on_search_complete)
        self.search_thread.error.connect(self.on_search_error)
        self.search_thread.start()

    def on_search_complete(self, results):
        self.result_list.clear()
        for extension in results:
            # 创建一个空的项目，数据将在委托中使用
            item = QListWidgetItem()  # 修改这里，直接使用QListWidgetItem
            # 存储插件信息作为item的数据
            item.setData(Qt.UserRole, extension)
            self.result_list.addItem(item)

        self.search_button.setEnabled(True)
        self.statusBar().showMessage(f'搜索完成，找到 {len(results)} 个结果')

    def on_search_error(self, error_msg):
        QMessageBox.critical(self, '错误', f'搜索失败: {error_msg}')
        self.search_button.setEnabled(True)
        self.statusBar().showMessage('搜索失败')

    def download_extension(self):
        current_item = self.result_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, '警告', '请先选择一个插件')
            return

        extension_data = current_item.data(Qt.UserRole)
        if not extension_data:
            return

        self.download_button.setEnabled(False)
        self.statusBar().showMessage('正在下载...')

        self.download_thread = DownloadThread(extension_data)
        self.download_thread.finished.connect(self.on_download_complete)
        self.download_thread.error.connect(self.on_download_error)
        self.download_thread.start()

    def on_download_complete(self, file_path):
        QMessageBox.information(self, '成功', f'插件已下载到: {file_path}')
        self.download_button.setEnabled(True)
        self.statusBar().showMessage('下载完成')

    def on_download_error(self, error_msg):
        QMessageBox.critical(self, '错误', f'下载失败: {error_msg}')
        self.download_button.setEnabled(True)
        self.statusBar().showMessage('下载失败')

class SearchThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query):
        super().__init__()
        self.query = query

    def run(self):
        try:
            url = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery"

            payload = {
                "filters": [{
                    "criteria": [{
                        "filterType": 8,
                        "value": "Microsoft.VisualStudio.Code"
                    }, {
                        "filterType": 10,
                        "value": self.query
                    }]
                }],
                "flags": 870
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()
            results = response.json()['results'][0]['extensions']
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

class DownloadThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, extension_data):
        super().__init__()
        self.extension_data = extension_data

    def run(self):
        try:
            publisher_name = self.extension_data['publisher']['publisherName']
            extension_name = self.extension_data['extensionName']
            version = self.extension_data['versions'][0]['version']

            url = f'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/{publisher_name}/vsextensions/{extension_name}/{version}/vspackage'
            headers = {
                'Accept': 'application/octet-stream'
            }

            response = requests.get(url, headers=headers)
            response.raise_for_status()

            # 创建下载目录
            if not os.path.exists('downloads'):
                os.makedirs('downloads')

            file_name = f'{publisher_name}.{extension_name}-{version}.vsix'
            file_path = os.path.join('downloads', file_name)

            with open(file_path, 'wb') as f:
                f.write(response.content)

            self.finished.emit(file_path)
        except Exception as e:
            self.error.emit(str(e))

def main():
    app = QApplication(sys.argv)
    
    # 应用现代化暗色主题
    qtmodern.styles.dark(app)
    
    # 创建主窗口
    window = VSCodeExtensionDownloader()
    # 使用 qtmodern 包装主窗口
    modern_window = qtmodern.windows.ModernWindow(window)
    modern_window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()