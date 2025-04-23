# Hedge Detection Web Application

This web application analyzes trading data to identify potential hedge pairs between trades, calculates confidence scores, and presents results visually.

## Local Development with Streamlit

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the Streamlit application:
   ```
   streamlit run streamlit_app.py
   ```
5. Access the application at http://localhost:8501

## Deployment to Streamlit Cloud

1. Push your code to GitHub:
   ```
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/your-repo-name.git
   git push -u origin main
   ```

2. Go to [Streamlit Cloud](https://streamlit.io/cloud)
3. Sign in with GitHub
4. Click "New app"
5. Enter:
   - Repository: your GitHub repository
   - Branch: main
   - Main file path: streamlit_app.py
6. Click "Deploy"

Your application will be accessible via a URL provided by Streamlit Cloud.

## Deployment Options

### Render

1. Create a [Render](https://render.com) account
2. Create a new Web Service
3. Connect your GitHub repository
4. Set the following:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
5. Click "Create Web Service"

### Heroku

1. Create a [Heroku](https://heroku.com) account
2. Install Heroku CLI and login:
   ```
   heroku login
   ```
3. Create a new app:
   ```
   heroku create your-app-name
   ```
4. Push to Heroku:
   ```
   git push heroku main
   ```

### Railway

1. Create a [Railway](https://railway.app) account
2. Create a new project
3. Connect your GitHub repository
4. Add a Python service
5. Railway will auto-detect the Procfile and requirements

## Notes

- The free tier of Streamlit Cloud has a 1GB RAM limit which may be sufficient for small to medium datasets
- For larger CSV files (>50MB), you may need to upgrade to Streamlit Teams or use alternative hosting
- The application is configured with a maximum upload size of 200MB in the `.streamlit/config.toml` file
- The application requires substantial memory for processing large CSV files
- Consider using a service with at least 1GB RAM for production use
- The free tier of most hosting services may not be sufficient for large files 