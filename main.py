import pymupdf as fitz
import numpy as np
from tqdm import tqdm


def is_color_image(image, saturation_threshold=0.35, color_fraction_threshold=0.001):
    image = image.convert('RGB')
    pixels = np.array(image) / 255.0  # 归一化像素值到[0,1]范围

    # 将RGB转换为HSV
    max_rgb = np.max(pixels, axis=2)
    min_rgb = np.min(pixels, axis=2)
    delta = max_rgb - min_rgb

    # 饱和度
    saturation = delta / (max_rgb + 1e-7)  # 防止除以零

    # 判断饱和度大于阈值的彩色像素
    color_pixels = saturation > saturation_threshold
    color_fraction = np.mean(color_pixels)

    return color_fraction > color_fraction_threshold


def is_color_page(page):
    """
    Check if a page is a color page.
    """
    # Render page to a pixmap
    pix = page.get_pixmap()
    # Convert pixmap to an image
    img = pix.tobytes("png")


    # Create an image object using PIL
    from PIL import Image
    from io import BytesIO
    image = Image.open(BytesIO(img))

    return is_color_image(image)


def split_pdf(input_pdf_path, output_color_pdf_path, output_bw_pdf_path, is_double_sized_printing):
    # Open the input PDF
    doc = fitz.open(input_pdf_path)

    # Create new PDFs for color and black & white pages
    color_doc = fitz.open()
    bw_doc = fitz.open()

    # Save color and bw pages number
    color_pages = []
    bw_pages = []

    # Iterate over each page in the input PDF
    for page_num in tqdm(range(len(doc))):
        page = doc.load_page(page_num)

        # Check if the page is a color page
        if is_color_page(page):
            color_pages.append(page_num)

    # Handle double sized printing
    if is_double_sized_printing:
        for page_num in color_pages:
            if page_num % 2 == 0 and page_num + 1 not in color_pages and page_num + 1 < len(doc):
                color_pages.append(page_num + 1)
            if page_num % 2 == 1 and page_num - 1 not in color_pages and page_num - 1 > 0:
                color_pages.append(page_num - 1)

    # Insert BW Pages
    for page_num in range(len(doc)):
        if page_num not in color_pages:
            bw_pages.append(page_num)

    # Insert PDF pages
    for page_num in sorted(color_pages):
        color_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)

    for page_num in sorted(bw_pages):
        bw_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)

    # Save the new PDFs
    color_doc.save(output_color_pdf_path)
    bw_doc.save(output_bw_pdf_path)

    # Close all documents
    doc.close()
    color_doc.close()
    bw_doc.close()

if __name__ == '__main__':
    INPUT_PDF_PATH = 'example.pdf'  # 待转换的PDF路径
    OUTPUT_COLOR_PDF_PATH = 'color_pages.pdf'  # 彩色部分PDF输出路径
    OUTPUT_BW_PDF_PATH = 'bw_pages.pdf'  # 黑白部分PDF输出路径
    IS_DOUBLE_SIZED_PRINTING = True  # 是否双面打印

    split_pdf(INPUT_PDF_PATH, OUTPUT_COLOR_PDF_PATH, OUTPUT_BW_PDF_PATH, IS_DOUBLE_SIZED_PRINTING)
