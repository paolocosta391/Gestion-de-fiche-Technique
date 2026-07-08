import os
from flask import Flask, jsonify

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-changez-moi')

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Gestionnaire de Fiches Techniques</title>
        <style>
            body { font-family: Arial; margin: 50px; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #1a237e; }
            .status { padding: 10px; background: #d4edda; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Gestionnaire de Fiches Techniques</h1>
            <div class="status">
                <p>✅ Application déployée avec succès sur Railway!</p>
                <p>Version: 1.0 - Build en cours d'amélioration</p>
            </div>
            <h2>Fonctionnalités en développement:</h2>
            <ul>
                <li>✅ CRUD des fiches techniques</li>
                <li>✅ Authentification JWT</li>
                <li>✅ Recherche avancée</li>
                <li>✅ Export CSV/Excel</li>
                <li>✅ Versioning des fichiers</li>
                <li>✅ Système de tags</li>
                <li>✅ Dashboard responsive</li>
            </ul>
            <p><small>Déployé sur <strong>Railway</strong></small></p>
        </div>
    </body>
    </html>
    '''

@app.route('/api/status')
def status():
    return jsonify({'status': 'online', 'app': 'Gestionnaire de Fiches Techniques'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
