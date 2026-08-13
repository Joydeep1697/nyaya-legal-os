@echo off
setlocal
cd /d "D:\Nova Legal\Indian Legal"

if not exist ".classifiervenv\Scripts\python.exe" (
    echo Missing .classifiervenv
    exit /b 1
)

".classifiervenv\Scripts\python.exe" ^
  "D:\Nova Legal\Indian Legal\nova_legal_classifier.py" ^
  --raw "D:\Nova Legal\Indian Legal\raw" ^
  --category "D:\Nova Legal\Indian Legal\Category" ^
  --database "D:\Nova Legal\Indian Legal\category_registry.sqlite3" ^
  --reports "D:\Nova Legal\Indian Legal\classification_reports" ^
  --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe" ^
  --ocr-language "eng" ^
  --use-nvidia-fallback

exit /b %ERRORLEVEL%
