# Gestionnaire de Fiches Techniques

Une application Flask complète pour gérer les fiches techniques avec fonctionnalités avancées.

## 🎯 Fonctionnalités

- ✅ **CRUD complet** : Créer, lire, modifier, supprimer des fiches
- ✅ **Authentification JWT** : Login/Register avec tokens sécurisés
- ✅ **Recherche avancée** : Recherche SQL et Elasticsearch (optionnel)
- ✅ **Export** : CSV et Excel
- ✅ **Versioning** : Historique des versions des fiches
- ✅ **Système de tags** : Tagging avancé avec couleurs
- ✅ **Notifications temps réel** : WebSocket pour les mises à jour
- ✅ **Statistiques** : Dashboard avec métriques
- ✅ **Interface web** : UI moderne et responsive

## 🚀 Démarrage rapide

### Prérequis
- Python 3.9+
- pip

### Installation

```bash
# Cloner le repo
git clone https://github.com/paolocosta391/Gestion-de-fiche-Technique.git
cd Gestion-de-fiche-Technique

# Créer un environnement virtuel
python -m venv venv

# Activer l'environnement virtuel
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```

### Lancer l'application

```bash
python deepseek_python_20260708_112ed6.py
```

L'application sera disponible à : **http://localhost:5000**

## 👤 Compte par défaut

- **Username** : admin
- **Password** : admin

## 📋 Configuration

### Variables d'environnement

```bash
PORT=5000              # Port d'écoute (par défaut 5000)
FLASK_ENV=production   # Mode production
```

### Base de données

L'application utilise **SQLite** par défaut (`fiches_complet.db`). 
Pour changer, modifiez la ligne dans le fichier principal :

```python
engine = create_engine('sqlite:///fiches_complet.db')
```

## 📁 Structure du projet

```
.
├── deepseek_python_20260708_112ed6.py  # Application principale
├── fiches_complet.db                    # Base de données SQLite
├── requirements.txt                     # Dépendances Python
├── Procfile                             # Configuration de déploiement
├── runtime.txt                          # Version de Python
└── README.md                            # Ce fichier
```

## 🛠️ Technologies

- **Backend** : Flask, Flask-CORS, Flask-SocketIO
- **Base de données** : SQLAlchemy, SQLite
- **Authentification** : JWT
- **Frontend** : HTML5, CSS3, JavaScript vanilla
- **WebSocket** : Socket.IO
- **Export** : CSV, Excel (Pandas optionnel)

## 🚢 Déploiement

### Sur Railway

1. Créer un compte sur [railway.app](https://railway.app)
2. Connecter le dépôt GitHub
3. Railway détecte automatiquement le `Procfile`
4. L'application sera déployée automatiquement

### Sur Render

1. Créer un compte sur [render.com](https://render.com)
2. Créer un "New Web Service"
3. Connecter le GitHub
4. Configuration recommandée :
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `python deepseek_python_20260708_112ed6.py`

## ⚠️ Avant le déploiement en production

1. Changer la `SECRET_KEY` dans le code
2. Désactiver le mode debug
3. Configurer une vraie base de données (PostgreSQL recommandé)
4. Ajouter les variables d'environnement sensibles

## 📝 Licence

MIT

## 👨‍💻 Auteur

Paolo Costa

---

Pour toute question ou problème, ouvrez une issue GitHub.
