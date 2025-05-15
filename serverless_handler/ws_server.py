#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import json
import os
import base64
import uuid
import numpy as np
from io import BytesIO
from PIL import Image
import upyun
import toml
import fitz
from aiohttp import web, WSMsgType
import pathlib

# 加载配置文件
def load_config():
    config_path = "./config.toml"
    return toml.load(config_path)

config = load_config()

# UPYUN 配置
UPYUN_SERVICE_NAME = config['upyun']['service_name']
UPYUN_OPERATOR_NAME = config['upyun']['operator_name']
UPYUN_OPERATOR_PASSWORD = config['upyun']['operator_password']
UPYUN_DOMAIN = config['upyun']['domain']

# WebSocket消息大小限制
MAX_MESSAGE_SIZE = config['websocket']['max_message_size']

# 创建临时文件夹
def ensure_tmp_dir():
    tmp_dir = "tmp"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    return tmp_dir

# 判断是否为彩色图像
def is_color_image(image, saturation_threshold=0.35, color_fraction_threshold=0.001):
    image = image.convert('RGB')
    pixels = np.array(image) / 255.0
    max_rgb = np.max(pixels, axis=2)
    min_rgb = np.min(pixels, axis=2)
    delta = max_rgb - min_rgb
    saturation = delta / (max_rgb + 1e-7)
    color_pixels = saturation > saturation_threshold
    color_fraction = np.mean(color_pixels)
    return color_fraction > color_fraction_threshold

# 判断页面是否为彩色
def is_color_page(page, saturation_threshold=0.35, color_fraction_threshold=0.001):
    pix = page.get_pixmap()
    img = pix.tobytes("png")
    image = Image.open(BytesIO(img))
    return is_color_image(image, saturation_threshold, color_fraction_threshold)

# 上传文件到又拍云
async def _upload_to_upyun_with_overwrite(up_instance, remote_path, data_stream, domain):
    try:
        try:
            up_instance.getinfo(remote_path)
            up_instance.delete(remote_path)
        except Exception:
            pass
        data_stream.seek(0)
        up_instance.put(remote_path, data_stream, checksum=True)
        return f"https://{domain}/{remote_path.lstrip('/')}"
    except Exception as e:
        raise

# 分割PDF为彩色和黑白两部分
async def split_pdf(input_pdf_path, session_id, is_double_sized_printing,
                    saturation_threshold=0.35, color_fraction_threshold=0.001, websocket=None):
    up = upyun.UpYun(UPYUN_SERVICE_NAME, UPYUN_OPERATOR_NAME, UPYUN_OPERATOR_PASSWORD)
    doc = fitz.open(input_pdf_path)
    color_doc = fitz.open()
    bw_doc = fitz.open()
    color_pages = []
    bw_pages = []
    total_pages = len(doc)

    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        if is_color_page(page, saturation_threshold, color_fraction_threshold):
            color_pages.append(page_num)
        if websocket:
            progress = {
                "type": "progress",
                "current": page_num + 1,
                "total": total_pages,
                "percentage": (page_num + 1) / total_pages * 100
            }
            await websocket.send_json(progress)
            await asyncio.sleep(0.01)

    if is_double_sized_printing:
        additional = []
        for page_num in color_pages:
            if page_num % 2 == 0 and page_num + 1 < total_pages and page_num + 1 not in color_pages:
                additional.append(page_num + 1)
            if page_num % 2 == 1 and page_num - 1 >= 0 and page_num - 1 not in color_pages:
                additional.append(page_num - 1)
        color_pages.extend(additional)
        color_pages = sorted(set(color_pages))

    for i in range(total_pages):
        if i not in color_pages:
            bw_pages.append(i)

    for page_num in sorted(color_pages):
        color_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
    for page_num in sorted(bw_pages):
        bw_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)

    color_pdf_url = None
    bw_pdf_url = None

    if color_pages:
        color_io = BytesIO()
        color_doc.save(color_io, garbage=4, deflate=True)
        color_remote_path = f"{session_id}/{session_id}_color.pdf"
        try:
            up.mkdir(session_id)
        except Exception:
            pass
        color_pdf_url = await _upload_to_upyun_with_overwrite(up, color_remote_path, color_io, UPYUN_DOMAIN)
        color_io.close()

    if bw_pages:
        bw_io = BytesIO()
        bw_doc.save(bw_io, garbage=4, deflate=True)
        bw_remote_path = f"{session_id}/{session_id}_bw.pdf"
        try:
            up.mkdir(session_id)
        except Exception:
            pass
        bw_pdf_url = await _upload_to_upyun_with_overwrite(up, bw_remote_path, bw_io, UPYUN_DOMAIN)
        bw_io.close()

    doc.close()
    color_doc.close()
    bw_doc.close()

    return {
        "color_pdf_url": color_pdf_url,
        "bw_pdf_url": bw_pdf_url,
        "color_pages_count": len(color_pages),
        "bw_pages_count": len(bw_pages),
        "total_pages": total_pages
    }

# WebSocket 处理函数
async def websocket_handler(request):
    ws = web.WebSocketResponse(max_msg_size=MAX_MESSAGE_SIZE)
    await ws.prepare(request)
    
    session_id = str(uuid.uuid4())
    tmp_dir = ensure_tmp_dir()
    client_files = {}
    chunk_buffers = {}

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type", "")
                    if msg_type == "upload":
                        file_name = data.get("fileName", "document.pdf")
                        chunk_index = data.get("chunkIndex")
                        total_chunks = data.get("totalChunks")
                        is_last_chunk = data.get("isLastChunk", False)

                        if chunk_index is not None and total_chunks is not None:
                            file_data = data.get("data", "").split(",")[1]
                            if file_name not in chunk_buffers:
                                chunk_buffers[file_name] = [None] * total_chunks
                            chunk_buffers[file_name][chunk_index] = file_data
                            if is_last_chunk or all(chunk is not None for chunk in chunk_buffers[file_name]):
                                if not all(chunk is not None for chunk in chunk_buffers[file_name]):
                                    await ws.send_json({
                                        "type": "error",
                                        "message": "文件上传不完整"
                                    })
                                    continue
                                combined = b"".join([base64.b64decode(c) for c in chunk_buffers[file_name]])
                                file_path = os.path.join(tmp_dir, f"{session_id}_{file_name}")
                                with open(file_path, "wb") as f:
                                    f.write(combined)
                                client_files["input_pdf"] = file_path
                                del chunk_buffers[file_name]
                                await ws.send_json({
                                    "type": "upload_response",
                                    "status": "success",
                                    "message": f"文件上传成功: {file_name}",
                                    "filename": file_name
                                })
                        else:
                            file_data = data.get("data", "").split(",")[1]
                            file_path = os.path.join(tmp_dir, f"{session_id}_{file_name}")
                            decoded = base64.b64decode(file_data)
                            with open(file_path, "wb") as f:
                                f.write(decoded)
                            client_files["input_pdf"] = file_path
                            await ws.send_json({
                                "type": "upload_response",
                                "status": "success",
                                "message": f"文件上传成功: {file_name}",
                                "filename": file_name
                            })

                    elif msg_type == "process":
                        if "input_pdf" not in client_files:
                            await ws.send_json({
                                "type": "error",
                                "message": "请先上传PDF文件"
                            })
                            continue
                        result = await split_pdf(
                            client_files["input_pdf"],
                            session_id,
                            data.get("isDoubleSided", True),
                            float(data.get("saturationThreshold", 0.35)),
                            float(data.get("colorFractionThreshold", 0.001)),
                            ws
                        )
                        client_files["color_pdf_url"] = result["color_pdf_url"]
                        client_files["bw_pdf_url"] = result["bw_pdf_url"]
                        await ws.send_json({
                            "type": "process_complete",
                            "color_pages": result["color_pages_count"],
                            "bw_pages": result["bw_pages_count"],
                            "total_pages": result["total_pages"],
                            "color_pdf_url": result["color_pdf_url"],
                            "bw_pdf_url": result["bw_pdf_url"]
                        })

                    elif msg_type == "download":
                        file_type = data.get("fileType", "")
                        if file_type not in ["color", "bw"]:
                            await ws.send_json({
                                "type": "error",
                                "message": "文件类型必须是 color 或 bw"
                            })
                            continue
                        url_key = f"{file_type}_pdf_url"
                        if url_key in client_files:
                            await ws.send_json({
                                "type": "file_link",
                                "fileType": file_type,
                                "url": client_files[url_key]
                            })
                        else:
                            await ws.send_json({
                                "type": "error",
                                "message": f"{file_type} PDF 未找到"
                            })
                    else:
                        await ws.send_json({
                            "type": "error",
                            "message": f"未知消息类型: {msg_type}"
                        })
                except Exception as e:
                    await ws.send_json({
                        "type": "error",
                        "message": f"内部处理错误: {str(e)}"
                    })
    finally:
        print(f"清理会话 {session_id}")
        if "input_pdf" in client_files and os.path.exists(client_files["input_pdf"]):
            try:
                os.remove(client_files["input_pdf"])
            except Exception as e:
                print(f"删除文件失败: {e}")
        try:
            up = upyun.UpYun(UPYUN_SERVICE_NAME, UPYUN_OPERATOR_NAME, UPYUN_OPERATOR_PASSWORD)
            for file_type in ["color", "bw"]:
                url_key = f"{file_type}_pdf_url"
                if url_key in client_files:
                    up.delete(f"{session_id}/{session_id}_{file_type}.pdf")
            up.delete(session_id)
        except Exception as e:
            print(f"清理又拍云文件失败: {e}")
    
    return ws

# 启动服务器
async def main():
    ensure_tmp_dir()
    
    # 创建应用
    app = web.Application()
    
    # 设置路由
    # 静态文件路由
    current_dir = pathlib.Path(__file__).parent
    static_path = current_dir / 'static'
    app.router.add_static('/', static_path)
    
    # WebSocket 路由
    app.router.add_get('/ws', websocket_handler)
    
    # 启动服务器
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 9000)
    await site.start()
    
    print(f"服务器已启动在 http://0.0.0.0:9000")
    print(f"WebSocket 端点: ws://0.0.0.0:9000/ws")
    
    # 保持服务器运行
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
