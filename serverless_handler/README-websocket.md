# PDF 彩色和黑白页面分离器 WebSocket 服务器

这是一个基于WebSocket的PDF彩色和黑白页面分离器，它允许用户通过浏览器上传PDF文件，指定参数进行处理，并下载分离后的PDF文件。

## 功能特点

1. 通过WebSocket实时上传PDF文件
2. 支持自定义处理参数（双面打印模式、饱和度阈值、色彩比例阈值）
3. 实时显示处理进度
4. 处理结束后下载彩色页面和黑白页面的PDF文件
5. 断开连接后自动清理临时文件

## 安装依赖

确保已安装以下Python库：

```bash
pip install pymupdf numpy tqdm websockets Pillow
```

## 使用方法

1. 运行服务器脚本：

```bash
python run_server.py
```

2. 脚本会自动打开浏览器并访问 http://localhost:8000 页面，如果未自动打开，请手动访问。

3. 使用界面操作：
   - 点击"连接到服务器"按钮，连接WebSocket服务器
   - 选择并上传PDF文件
   - 设置处理参数（双面打印模式、饱和度阈值、色彩比例阈值）
   - 点击"开始处理"按钮，观察处理进度
   - 处理完成后，点击下载按钮获取分离后的PDF文件

## 代码结构

- `run_server.py`: 启动脚本，运行WebSocket服务器和HTTP静态文件服务器
- `serverless_handler/ws_server.py`: WebSocket服务器实现，处理客户端消息和PDF分离逻辑
- `index.html`: 客户端界面，用于与WebSocket服务器交互

## WebSocket通信协议

客户端和服务器之间使用JSON格式交换消息，主要消息类型如下：

1. 上传文件：
```json
{
  "type": "upload",
  "fileName": "文件名.pdf",
  "data": "base64编码的PDF数据"
}
```

2. 处理请求：
```json
{
  "type": "process",
  "isDoubleSided": true,
  "saturationThreshold": 0.35,
  "colorFractionThreshold": 0.001
}
```

3. 下载请求：
```json
{
  "type": "download",
  "fileType": "color"  // 或 "bw" 用于黑白PDF
}
```

4. 进度更新（服务器发送）：
```json
{
  "type": "progress",
  "current": 1,
  "total": 10,
  "percentage": 10.0
}
```

5. 处理完成（服务器发送）：
```json
{
  "type": "process_complete",
  "color_pages": 5,
  "bw_pages": 5,
  "total_pages": 10
}
```

6. 文件数据（服务器发送）：
```json
{
  "type": "file_data",
  "fileType": "color",
  "data": "base64编码的PDF数据"
}
```

## 注意事项

1. 临时文件存储在`tmp`文件夹中，WebSocket连接断开后会自动清理。
2. 大型PDF文件可能导致内存消耗较大，请确保系统有足够的内存。
3. 处理大型PDF时可能需要较长时间，请耐心等待。

## 技术原理

1. WebSocket服务器使用`websockets`库实现，支持实时双向通信。
2. PDF处理使用`PyMuPDF`(fitz)库处理PDF文件和页面。
3. 图像处理使用`numpy`和`PIL`库分析色彩信息。
4. 使用饱和度和色彩比例阈值判断页面是否为彩色页面。 