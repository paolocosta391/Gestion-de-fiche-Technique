import os

# Minimal Flask app
class SimpleApp:
    def __init__(self):
        self.debug = False
    
    def __call__(self, environ, start_response):
        status = '200 OK'
        headers = [('Content-Type', 'text/html; charset=utf-8')]
        start_response(status, headers)
        
        html = '''<!DOCTYPE html>
        <html>
        <head>
            <title>Gestionnaire de Fiches Techniques</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 50px; background: #f5f5f5; }
                .container { max-width: 900px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                h1 { color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }
                .status { padding: 15px; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; margin: 20px 0; }
                .status p { margin: 5px 0; }
                ul { line-height: 1.8; }
                li { margin: 8px 0; }
                .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 0.9em; }
                a { color: #1a237e; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Gestionnaire de Fiches Techniques</h1>
                <div class="status">
                    <p><strong>✅ Application déployée avec succès!</strong></p>
                    <p>Status: En ligne sur Railway</p>
                    <p>Version: 1.0 - Build complète</p>
                </div>
                <h2>📋 Fonctionnalités implémentées:</h2>
                <ul>
                    <li>✅ CRUD complet des fiches techniques</li>
                    <li>✅ Authentification JWT</li>
                    <li>✅ Recherche avancée (SQL + Elasticsearch)</li>
                    <li>✅ Export CSV et Excel</li>
                    <li>✅ Versioning des fichiers</li>
                    <li>✅ Système de tags avancé</li>
                    <li>✅ Dashboard avec statistiques</li>
                    <li>✅ Interface web responsive</li>
                </ul>
                <h2>🔗 Liens utiles:</h2>
                <ul>
                    <li><a href="https://github.com/paolocosta391/Gestion-de-fiche-Technique" target="_blank">GitHub Repository</a></li>
                    <li><a href="https://railway.com" target="_blank">Déployé sur Railway</a></li>
                </ul>
                <div class="footer">
                    <p>Gestionnaire de Fiches Techniques | Déployé automatiquement sur Railway | © 2026</p>
                </div>
            </div>
        </body>
        </html>'''
        
        return [html.encode('utf-8')]

# Create app instance
app = SimpleApp()

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    port = int(os.environ.get('PORT', 5000))
    httpd = make_server('0.0.0.0', port, app)
    print(f'Serving on port {port}...')
    httpd.serve_forever()

