# Color and Black & White Separator for PDF

This tool is used to separate color and black & white pages from a PDF file into two separate PDF files.

## Languages
<a href="./README-zh_cn.md">简体中文</a>

## Installation Instructions

1. Install the libraries:

```bash
pip install pymupdf
pip install numpy
pip install tqdm
```

## Usage Guide

1. Place the PDF file to be separated in `INPUT_PDF_PATH`.
2. Run the `main.py` script.

```bash
python main.py
```
3. Choose whether to use double-sized printing mode by configuring `IS_DOUBLE_SIZED_PRINTING`
4. The separated color pages will be saved in `color_pages.pdf`, and black & white pages will be saved in `bw_pages.pdf`.

## Contributing

Contributions are welcome! If you find any issues or have any suggestions, please raise an issue. If you'd like to contribute code, please fork this repository and submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
