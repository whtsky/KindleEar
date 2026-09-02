@echo off
rem KindleEar unit test launcher, works from any drive/path
rem Switch to the KindleEar root directory (this bat is in the tests subfolder;
rem %~dp0 is the bat's own directory, /d switches the drive)
cd /d "%~dp0.."
set DATABASE_URL=sqlite:///database.db
rem temp/webshelf follow the drive the project is on, consistent with run_flask.bat
set KE_TEMP_DIR=%~d0\temp
set EBOOK_SAVE_DIR=%~d0\webshelf
set DICTIONARY_DIR=%~d0\webshelf
set APP_DOMAIN=http://localhost:5000/
if not exist "%KE_TEMP_DIR%" mkdir "%KE_TEMP_DIR%"
if not exist "%EBOOK_SAVE_DIR%" mkdir "%EBOOK_SAVE_DIR%"
python tests\runtests.py
