cd /d "%~dp0.."
pybabel extract -F tools\babel.cfg --ignore-dirs lib --ignore-dirs tests -o application\translations\messages.pot .
pybabel update -i application\translations\messages.pot -d application\translations
pause
