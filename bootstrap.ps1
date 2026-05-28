Write-Host "=== BOOTSTRAPPING RASTI PROJECT ==="

# ----------------------------
# BACKEND SETUP
# ----------------------------
Write-Host "Setting up Backend..."

cd .\rasti-backend\current_project

python -m venv venv
.\venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
pip install djangorestframework-simplejwt

python manage.py migrate

Write-Host "Backend setup complete ✅"

# ----------------------------
# FRONTEND SETUP
# ----------------------------
Write-Host "Setting up Frontend..."

cd ..\..\rasti-frontend

npm install

Write-Host "Frontend setup complete ✅"

Write-Host "=== SETUP COMPLETE ==="
Write-Host "To run backend:"
Write-Host "cd rasti-backend\current_project"
Write-Host ".\venv\Scripts\activate"
Write-Host "python manage.py runserver"

Write-Host "To run frontend:"
Write-Host "cd rasti-frontend"
Write-Host "npm run dev"