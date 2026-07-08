"""
================================================================================
GESTIONNAIRE DE FICHES TECHNIQUES - VERSION COMPLÈTE
================================================================================
Fichier unique contenant TOUTES les fonctionnalités :
1. CRUD complet des fiches techniques
2. Authentification JWT (login/register)
3. Recherche avancée (Elasticsearch + recherche SQL)
4. Export CSV et Excel
5. Versioning des fichiers
6. Système de tags avancé
7. Notifications en temps réel (WebSocket)
8. Statistiques
9. Interface web moderne et responsive
10. Drag & drop pour l'import
================================================================================
"""

import os
import sys
import uuid
import csv
import io
import json
import hashlib
import datetime
from functools import wraps
from flask import Flask, request, render_template_string, jsonify, send_file, make_response
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Table, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jwt
# pandas import moved locally to avoid startup failures on systems
# where compiled numpy wheels are blocked by policy. Pandas will be
# imported when needed (export to Excel).
from datetime import datetime, timedelta

# =================================================================================
# CONFIGURATION
# =================================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'votre_cle_secrete_tres_securisee_changez_moi_123456789'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'jpg', 'png', 'zip'}

# Création des dossiers
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# =================================================================================
# BASE DE DONNÉES
# =================================================================================

Base = declarative_base()
engine = create_engine('sqlite:///fiches_complet.db', connect_args={'check_same_thread': False})
Session = sessionmaker(bind=engine)

# =================================================================================
# MODÈLES
# =================================================================================

# Table de liaison Many-to-Many Fiche <-> Tag
fiche_tag = Table('fiche_tag', Base.metadata,
    Column('fiche_id', Integer, ForeignKey('fiches.id')),
    Column('tag_id', Integer, ForeignKey('tags.id'))
)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), default='user')
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M') if self.last_login else None
        }

class Tag(Base):
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True)
    nom = Column(String(50), unique=True, nullable=False)
    couleur = Column(String(7), default='#1a237e')
    description = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nom': self.nom,
            'couleur': self.couleur,
            'description': self.description
        }

class VersionFiche(Base):
    __tablename__ = 'versions_fiches'
    
    id = Column(Integer, primary_key=True)
    fiche_id = Column(Integer, ForeignKey('fiches.id'))
    version = Column(String(20))
    chemin_fichier = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    commentaire = Column(Text)
    auteur = Column(String(100))
    
    def to_dict(self):
        return {
            'id': self.id,
            'version': self.version,
            'date': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'commentaire': self.commentaire,
            'auteur': self.auteur
        }

class Notification(Base):
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    type = Column(String(50))
    message = Column(String(500))
    fiche_id = Column(Integer, ForeignKey('fiches.id'))
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'message': self.message,
            'fiche_id': self.fiche_id,
            'read': self.read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

class FicheTechnique(Base):
    __tablename__ = 'fiches'
    
    id = Column(Integer, primary_key=True)
    reference = Column(String(50), unique=True, nullable=False)
    nom = Column(String(200), nullable=False)
    description = Column(Text)
    categorie = Column(String(100))
    fabricant = Column(String(100))
    version_actuelle = Column(String(20), default='1.0')
    date_import = Column(DateTime, default=datetime.utcnow)
    chemin_fichier = Column(String(500))
    auteur = Column(String(100))
    
    # Relations
    tags_relation = relationship('Tag', secondary=fiche_tag, backref='fiches')
    historique_versions = relationship('VersionFiche', backref='fiche', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'reference': self.reference,
            'nom': self.nom,
            'description': self.description,
            'categorie': self.categorie,
            'fabricant': self.fabricant,
            'version_actuelle': self.version_actuelle,
            'date_import': self.date_import.strftime('%Y-%m-%d %H:%M'),
            'tags': [tag.nom for tag in self.tags_relation],
            'auteur': self.auteur,
            'nb_versions': len(self.historique_versions)
        }
    
    def get_tags_list(self):
        return [tag.nom for tag in self.tags_relation]
    
    def set_tags(self, tag_list, session):
        self.tags_relation.clear()
        for tag_name in tag_list:
            if tag_name.strip():
                tag = session.query(Tag).filter(Tag.nom == tag_name.strip()).first()
                if not tag:
                    tag = Tag(nom=tag_name.strip())
                    session.add(tag)
                    session.flush()
                self.tags_relation.append(tag)
    
    def ajouter_version(self, chemin_fichier, commentaire, auteur, session):
        parts = self.version_actuelle.split('.')
        if len(parts) == 2:
            nouveau_num = f"{parts[0]}.{int(parts[1]) + 1}"
        else:
            nouveau_num = "1.1"
        
        version = VersionFiche(
            fiche_id=self.id,
            version=nouveau_num,
            chemin_fichier=chemin_fichier,
            commentaire=commentaire,
            auteur=auteur
        )
        session.add(version)
        self.version_actuelle = nouveau_num
        self.chemin_fichier = chemin_fichier
        return version

# Création des tables
Base.metadata.create_all(engine)

# Crée un compte administrateur par défaut si nécessaire
session = Session()
if not session.query(User).filter(User.username == 'admin').first():
    admin = User(username='admin', email='admin@example.com', role='admin')
    admin.set_password('admin')
    session.add(admin)
    session.commit()
session.close()

# =================================================================================
# ELASTICSEARCH (Optionnel)
# =================================================================================

class SearchEngine:
    def __init__(self):
        self.enabled = False
        self.es = None
        self.index_name = 'fiches_techniques'
        try:
            from elasticsearch import Elasticsearch
            self.es = Elasticsearch(['http://localhost:9200'], timeout=30)
            if self.es.ping():
                self.enabled = True
                self._create_index()
                print("✅ Elasticsearch connecté")
            else:
                print("⚠️ Elasticsearch non disponible - recherche basique utilisée")
        except:
            print("⚠️ Elasticsearch non disponible - recherche basique utilisée")
    
    def _create_index(self):
        if not self.enabled:
            return
        try:
            if not self.es.indices.exists(index=self.index_name):
                mapping = {
                    'mappings': {
                        'properties': {
                            'id': {'type': 'integer'},
                            'reference': {'type': 'text', 'analyzer': 'french'},
                            'nom': {'type': 'text', 'analyzer': 'french', 'boost': 3},
                            'description': {'type': 'text', 'analyzer': 'french'},
                            'categorie': {'type': 'keyword'},
                            'fabricant': {'type': 'text', 'analyzer': 'french'},
                            'tags': {'type': 'text', 'analyzer': 'french'},
                            'date_import': {'type': 'date'},
                            'suggest': {'type': 'completion', 'analyzer': 'simple'}
                        }
                    }
                }
                self.es.indices.create(index=self.index_name, body=mapping)
        except:
            pass
    
    def index_fiche(self, fiche):
        if not self.enabled:
            return
        try:
            doc = {
                'id': fiche.id,
                'reference': fiche.reference,
                'nom': fiche.nom,
                'description': fiche.description or '',
                'categorie': fiche.categorie or '',
                'fabricant': fiche.fabricant or '',
                'tags': ','.join([tag.nom for tag in fiche.tags_relation]),
                'date_import': fiche.date_import.isoformat(),
                'suggest': {
                    'input': [fiche.nom, fiche.reference] + [tag.nom for tag in fiche.tags_relation],
                    'weight': 10
                }
            }
            self.es.index(index=self.index_name, id=fiche.id, body=doc)
        except:
            pass
    
    def search(self, query, categories=None, fabricants=None):
        if not self.enabled or not query:
            return None
        try:
            must_clauses = [{
                'multi_match': {
                    'query': query,
                    'fields': ['nom^3', 'reference^2', 'description', 'fabricant', 'tags'],
                    'fuzziness': 'AUTO'
                }
            }]
            
            filters = []
            if categories:
                filters.append({'terms': {'categorie': categories}})
            if fabricants:
                filters.append({'terms': {'fabricant': fabricants}})
            
            body = {
                'query': {'bool': {'must': must_clauses, 'filter': filters}},
                'size': 50
            }
            
            result = self.es.search(index=self.index_name, body=body)
            hits = []
            for hit in result['hits']['hits']:
                source = hit['_source']
                hits.append({
                    'id': source['id'],
                    'reference': source['reference'],
                    'nom': source['nom'],
                    'description': source['description'],
                    'categorie': source['categorie'],
                    'fabricant': source['fabricant'],
                    'tags': source['tags'].split(',') if source['tags'] else [],
                    'date_import': source['date_import'],
                    'score': hit['_score']
                })
            return {'total': result['hits']['total']['value'], 'results': hits}
        except:
            return None
    
    def delete_fiche(self, fiche_id):
        if not self.enabled:
            return
        try:
            self.es.delete(index=self.index_name, id=fiche_id, ignore=[404])
        except:
            pass

search_engine = SearchEngine()

# =================================================================================
# FONCTIONS UTILITAIRES
# =================================================================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def create_notification(user_id, type, message, fiche_id=None):
    session = Session()
    try:
        notification = Notification(
            user_id=user_id,
            type=type,
            message=message,
            fiche_id=fiche_id
        )
        session.add(notification)
        session.commit()
        socketio.emit('notification', {
            'user_id': user_id,
            'type': type,
            'message': message,
            'fiche_id': fiche_id
        }, room=str(user_id))
    except:
        session.rollback()
    finally:
        session.close()

def notify_all_users(message, type='info', fiche_id=None):
    session = Session()
    try:
        users = session.query(User).filter(User.is_active == True).all()
        for user in users:
            create_notification(user.id, type, message, fiche_id)
    finally:
        session.close()

# =================================================================================
# DÉCORATEURS D'AUTHENTIFICATION
# =================================================================================

def get_request_token():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1]
    token = request.args.get('token')
    if token:
        return token
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_request_token()
        if not token:
            return jsonify({'error': 'Authentification requise'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = data['user_id']
            request.user_role = data['role']
            request.username = data['username']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expiré'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token invalide'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.user_role != 'admin':
            return jsonify({'error': 'Accès réservé aux administrateurs'}), 403
        return f(*args, **kwargs)
    return decorated_function

# =================================================================================
# ROUTES API - AUTHENTIFICATION
# =================================================================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    if not username or not email or not password:
        return jsonify({'error': 'Nom d\'utilisateur, email et mot de passe requis'}), 400

    session = Session()
    if session.query(User).filter(User.username == username).first():
        session.close()
        return jsonify({'error': 'Nom d\'utilisateur déjà utilisé'}), 400
    if session.query(User).filter(User.email == email).first():
        session.close()
        return jsonify({'error': 'Email déjà utilisé'}), 400
    
    user = User(
        username=username,
        email=email,
        role=data.get('role', 'user')
    )
    user.set_password(password)
    session.add(user)
    session.commit()
    # Convert before closing session to avoid DetachedInstanceError
    user_data = user.to_dict()
    session.close()

    return jsonify({'message': 'Utilisateur créé avec succès', 'user': user_data}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    session = Session()
    
    user = session.query(User).filter(User.username == data['username']).first()
    if not user or not user.check_password(data['password']):
        session.close()
        return jsonify({'error': 'Identifiants invalides'}), 401
    
    user.last_login = datetime.utcnow()
    session.commit()
    token = jwt.encode({
        'user_id': user.id,
        'username': user.username,
        'role': user.role,
        'exp': datetime.utcnow() + timedelta(days=7)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    # Serialize user while session still attached
    user_data = user.to_dict()
    session.close()

    return jsonify({
        'token': token,
        'user': user_data
    })

@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    session = Session()
    user = session.query(User).get(request.user_id)
    if not user:
        session.close()
        return jsonify({'error': 'Utilisateur non trouvé'}), 404
    user_data = user.to_dict()
    session.close()
    return jsonify(user_data)

@app.route('/api/auth/users', methods=['GET'])
@login_required
@admin_required
def list_users():
    session = Session()
    users = session.query(User).all()
    users_data = [u.to_dict() for u in users]
    session.close()
    return jsonify(users_data)

# =================================================================================
# ROUTES API - FICHES TECHNIQUES
# =================================================================================

@app.route('/api/fiches', methods=['GET'])
@login_required
def get_fiches():
    session = Session()
    search = request.args.get('search', '')
    categorie = request.args.get('categorie', '')
    fabricant = request.args.get('fabricant', '')
    tag = request.args.get('tag', '')
    
    # Recherche avancée avec Elasticsearch
    query = session.query(FicheTechnique)
    if search and search_engine.enabled:
        categories = [categorie] if categorie else None
        fabricants = [fabricant] if fabricant else None
        es_results = search_engine.search(search, categories, fabricants)
        if es_results and es_results['total'] > 0:
            ids = [r['id'] for r in es_results['results']]
            query = session.query(FicheTechnique).filter(FicheTechnique.id.in_(ids))
            fiches = query.all()
            fiches_data = [f.to_dict() for f in fiches]
            session.close()
            return jsonify(fiches_data)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (FicheTechnique.nom.like(search_term)) |
            (FicheTechnique.reference.like(search_term)) |
            (FicheTechnique.fabricant.like(search_term)) |
            (FicheTechnique.description.like(search_term))
        )
    if categorie:
        query = query.filter(FicheTechnique.categorie == categorie)
    if fabricant:
        query = query.filter(FicheTechnique.fabricant == fabricant)
    if tag:
        query = query.join(FicheTechnique.tags_relation).filter(Tag.nom == tag)
    
    fiches = query.all()
    fiches_data = [f.to_dict() for f in fiches]
    session.close()
    return jsonify(fiches_data)

@app.route('/api/fiches/<int:id>', methods=['GET'])
@login_required
def get_fiche(id):
    session = Session()
    fiche = session.query(FicheTechnique).get(id)
    if not fiche:
        session.close()
        return jsonify({'error': 'Fiche non trouvée'}), 404

    data = fiche.to_dict()
    data['historique'] = [v.to_dict() for v in fiche.historique_versions]
    session.close()
    return jsonify(data)

@app.route('/api/fiches', methods=['POST'])
@login_required
def import_fiche():
    if 'fichier' not in request.files:
        return jsonify({'error': 'Aucun fichier'}), 400
    
    file = request.files['fichier']
    if file.filename == '':
        return jsonify({'error': 'Nom de fichier vide'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Format non supporté'}), 400
    
    filename = secure_filename(file.filename)
    unique_id = str(uuid.uuid4())[:8]
    saved_name = f"{unique_id}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
    file.save(filepath)
    
    session = Session()

    reference = request.form.get('reference', '').strip() or f"REF-{unique_id}"
    fiche = FicheTechnique(
        reference=reference,
        nom=request.form.get('nom', filename),
        description=request.form.get('description', ''),
        categorie=request.form.get('categorie', ''),
        fabricant=request.form.get('fabricant', ''),
        chemin_fichier=filepath,
        auteur=request.username
    )
    
    tags = request.form.get('tags', '').split(',')
    fiche.set_tags([t.strip() for t in tags if t.strip()], session)
    
    session.add(fiche)
    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        session.close()
        if 'UNIQUE constraint failed: fiches.reference' in str(e):
            return jsonify({'error': 'Référence déjà utilisée'}), 400
        return jsonify({'error': 'Erreur de base de données'}), 500
    
    search_engine.index_fiche(fiche)
    
    notify_all_users(
        f"Nouvelle fiche : {fiche.nom} ({fiche.reference})",
        'import',
        fiche.id
    )
    fiche_data = fiche.to_dict()
    fiche_id = fiche.id
    session.close()

    return jsonify({
        'message': 'Fiche importée avec succès',
        'id': fiche_id,
        'fiche': fiche_data
    }), 201

@app.route('/api/fiches/<int:id>', methods=['PUT'])
@login_required
def update_fiche(id):
    session = Session()
    fiche = session.query(FicheTechnique).get(id)
    if not fiche:
        session.close()
        return jsonify({'error': 'Fiche non trouvée'}), 404
    
    data = request.json
    
    if 'nom' in data:
        fiche.nom = data['nom']
    if 'description' in data:
        fiche.description = data['description']
    if 'categorie' in data:
        fiche.categorie = data['categorie']
    if 'fabricant' in data:
        fiche.fabricant = data['fabricant']
    if 'tags' in data:
        fiche.set_tags(data['tags'], session)
    
    session.commit()
    search_engine.index_fiche(fiche)
    fiche_data = fiche.to_dict()
    session.close()

    return jsonify({'message': 'Fiche mise à jour', 'fiche': fiche_data})

@app.route('/api/fiches/<int:id>/version', methods=['POST'])
@login_required
def ajouter_version(id):
    if 'fichier' not in request.files:
        return jsonify({'error': 'Aucun fichier'}), 400
    
    file = request.files['fichier']
    if file.filename == '':
        return jsonify({'error': 'Nom de fichier vide'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Format non supporté'}), 400
    
    session = Session()
    fiche = session.query(FicheTechnique).get(id)
    if not fiche:
        session.close()
        return jsonify({'error': 'Fiche non trouvée'}), 404
    
    filename = secure_filename(file.filename)
    unique_id = str(uuid.uuid4())[:8]
    saved_name = f"{unique_id}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
    file.save(filepath)
    
    commentaire = request.form.get('commentaire', f"Nouvelle version")
    version = fiche.ajouter_version(filepath, commentaire, request.username, session)
    
    session.commit()
    search_engine.index_fiche(fiche)

    notify_all_users(
        f"Nouvelle version {fiche.version_actuelle} pour {fiche.nom}",
        'update',
        fiche.id
    )

    version_data = version.to_dict()
    version_actuelle = fiche.version_actuelle
    session.close()
    return jsonify({
        'message': 'Version ajoutée',
        'version': version_data,
        'version_actuelle': version_actuelle
    })

@app.route('/api/fiches/<int:id>/download', methods=['GET'])
@login_required
def download_fiche(id):
    session = Session()
    fiche = session.query(FicheTechnique).get(id)
    if not fiche:
        session.close()
        return jsonify({'error': 'Fiche non trouvée'}), 404
    filepath = fiche.chemin_fichier
    session.close()

    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'Fichier non trouvé'}), 404

    return send_file(filepath, as_attachment=True)

@app.route('/api/fiches/<int:id>/versions/<int:version_id>/download', methods=['GET'])
@login_required
def download_version(id, version_id):
    session = Session()
    version = session.query(VersionFiche).get(version_id)
    if not version:
        session.close()
        return jsonify({'error': 'Version non trouvée'}), 404
    version_path = version.chemin_fichier
    session.close()

    if not version_path or not os.path.exists(version_path):
        return jsonify({'error': 'Version non trouvée'}), 404
    
    return send_file(version_path, as_attachment=True)

@app.route('/api/fiches/<int:id>', methods=['DELETE'])
@login_required
def delete_fiche(id):
    session = Session()
    fiche = session.query(FicheTechnique).get(id)
    if not fiche:
        session.close()
        return jsonify({'error': 'Fiche non trouvée'}), 404
    
    if os.path.exists(fiche.chemin_fichier):
        os.remove(fiche.chemin_fichier)
    
    for version in fiche.historique_versions:
        if os.path.exists(version.chemin_fichier):
            os.remove(version.chemin_fichier)
    
    session.delete(fiche)
    session.commit()
    search_engine.delete_fiche(id)
    
    notify_all_users(
        f"Fiche supprimée : {fiche.nom}",
        'delete',
        id
    )
    
    session.close()
    return jsonify({'message': 'Fiche supprimée'})

# =================================================================================
# ROUTES API - TAGS
# =================================================================================

@app.route('/api/tags', methods=['GET'])
@login_required
def get_tags():
    session = Session()
    tags = session.query(Tag).all()
    session.close()
    return jsonify([t.to_dict() for t in tags])

@app.route('/api/tags/popular', methods=['GET'])
@login_required
def get_popular_tags():
    session = Session()
    tags = session.query(Tag).all()
    result = []
    for tag in tags:
        count = len(tag.fiches)
        if count > 0:
            data = tag.to_dict()
            data['count'] = count
            result.append(data)
    result.sort(key=lambda x: x['count'], reverse=True)
    session.close()
    return jsonify(result[:20])

@app.route('/api/tags', methods=['POST'])
@login_required
@admin_required
def create_tag():
    data = request.json
    session = Session()
    
    if session.query(Tag).filter(Tag.nom == data['nom']).first():
        session.close()
        return jsonify({'error': 'Tag déjà existant'}), 400
    
    tag = Tag(
        nom=data['nom'],
        couleur=data.get('couleur', '#1a237e'),
        description=data.get('description', '')
    )
    session.add(tag)
    session.commit()
    session.close()
    return jsonify(tag.to_dict()), 201

# =================================================================================
# ROUTES API - NOTIFICATIONS
# =================================================================================

@app.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    session = Session()
    notifications = session.query(Notification).filter(
        Notification.user_id == request.user_id,
        Notification.read == False
    ).order_by(Notification.created_at.desc()).limit(50).all()
    session.close()
    return jsonify([n.to_dict() for n in notifications])

@app.route('/api/notifications/all', methods=['GET'])
@login_required
def get_all_notifications():
    session = Session()
    notifications = session.query(Notification).filter(
        Notification.user_id == request.user_id
    ).order_by(Notification.created_at.desc()).limit(100).all()
    session.close()
    return jsonify([n.to_dict() for n in notifications])

@app.route('/api/notifications/<int:id>/read', methods=['PUT'])
@login_required
def mark_notification_read(id):
    session = Session()
    notification = session.query(Notification).get(id)
    if notification and notification.user_id == request.user_id:
        notification.read = True
        session.commit()
    session.close()
    return jsonify({'message': 'Notification marquée comme lue'})

@app.route('/api/notifications/read-all', methods=['PUT'])
@login_required
def mark_all_notifications_read():
    session = Session()
    notifications = session.query(Notification).filter(
        Notification.user_id == request.user_id,
        Notification.read == False
    ).all()
    for n in notifications:
        n.read = True
    session.commit()
    session.close()
    return jsonify({'message': 'Toutes les notifications marquées comme lues'})

# =================================================================================
# ROUTES API - EXPORT
# =================================================================================

@app.route('/api/export/csv', methods=['GET'])
@login_required
def export_csv():
    session = Session()
    fiches = session.query(FicheTechnique).all()
    # Build rows while session is open
    rows = []
    for f in fiches:
        rows.append([
            f.reference,
            f.nom,
            f.description or '',
            f.categorie or '',
            f.fabricant or '',
            f.version_actuelle,
            ', '.join([t.nom for t in f.tags_relation]),
            f.date_import.strftime('%Y-%m-%d %H:%M'),
            f.auteur or ''
        ])
    session.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Référence', 'Nom', 'Description', 'Catégorie', 'Fabricant', 'Version', 'Tags', 'Date Import', 'Auteur'])
    for row in rows:
        writer.writerow(row)
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename=fiches_techniques.csv'
    return response

@app.route('/api/export/excel', methods=['GET'])
@login_required
def export_excel():
    session = Session()
    fiches = session.query(FicheTechnique).all()
    data = []
    for f in fiches:
        data.append({
            'Référence': f.reference,
            'Nom': f.nom,
            'Description': f.description or '',
            'Catégorie': f.categorie or '',
            'Fabricant': f.fabricant or '',
            'Version': f.version_actuelle,
            'Tags': ', '.join([t.nom for t in f.tags_relation]),
            'Date Import': f.date_import.strftime('%Y-%m-%d %H:%M'),
            'Auteur': f.auteur or ''
        })
    session.close()
    
    try:
        import pandas as pd
    except Exception as e:
        return jsonify({'error': 'Pandas (ou numpy) indisponible: ' + str(e)}), 500
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Fiches Techniques', index=False)
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = 'attachment; filename=fiches_techniques.xlsx'
    return response

# =================================================================================
# ROUTES API - STATISTIQUES
# =================================================================================

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    session = Session()
    
    total = session.query(FicheTechnique).count()
    categories = session.query(FicheTechnique.categorie, func.count(FicheTechnique.id)).group_by(FicheTechnique.categorie).all()
    fabricants = session.query(FicheTechnique.fabricant, func.count(FicheTechnique.id)).group_by(FicheTechnique.fabricant).all()
    
    session.close()
    
    return jsonify({
        'total_fiches': total,
        'categories': [{'nom': c[0] or 'Non catégorisé', 'count': c[1]} for c in categories],
        'fabricants': [{'nom': f[0] or 'Inconnu', 'count': f[1]} for f in fabricants]
    })

# =================================================================================
# WEBSOCKET
# =================================================================================

@socketio.on('connect')
def handle_connect():
    token = request.args.get('token')
    if token:
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            join_room(str(data['user_id']))
            emit('connected', {'message': 'Connecté aux notifications', 'user': data['username']})
        except jwt.InvalidTokenError:
            pass

@socketio.on('subscribe')
def handle_subscribe(data):
    token = request.args.get('token')
    if token:
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            join_room(str(payload['user_id']))
            emit('subscribed', {'message': 'Abonné aux notifications'})
        except jwt.InvalidTokenError:
            pass

# =================================================================================
# INTERFACE WEB (HTML complet intégré)
# =================================================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gestionnaire de Fiches Techniques</title>
    <style>
        /* ===== RESET & BASE ===== */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; }
        
        /* ===== LOGIN ===== */
        #loginPage { display: flex; justify-content: center; align-items: center; min-height: 100vh; background: linear-gradient(135deg, #1a237e, #283593); }
        .login-container { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }
        .login-container h1 { color: #1a237e; text-align: center; margin-bottom: 30px; }
        .login-container .form-group { margin-bottom: 20px; }
        .login-container .form-group label { display: block; margin-bottom: 5px; color: #555; font-weight: 500; }
        .login-container .form-group input { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 16px; transition: border-color 0.3s; }
        .login-container .form-group input:focus { border-color: #1a237e; outline: none; }
        .login-container .btn { width: 100%; padding: 12px; background: #1a237e; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: background 0.3s; }
        .login-container .btn:hover { background: #0d1457; }
        .login-container .register-link { text-align: center; margin-top: 20px; color: #666; }
        .login-container .register-link a { color: #1a237e; text-decoration: none; font-weight: 600; cursor: pointer; }
        .login-container .error { background: #ffebee; color: #c62828; padding: 10px; border-radius: 8px; margin-bottom: 20px; display: none; }
        .login-container .tabs { display: flex; margin-bottom: 30px; border-bottom: 2px solid #e0e0e0; }
        .login-container .tabs button { flex: 1; padding: 10px; background: transparent; border: none; font-size: 16px; font-weight: 600; color: #888; cursor: pointer; transition: all 0.3s; border-bottom: 3px solid transparent; }
        .login-container .tabs button.active { color: #1a237e; border-bottom-color: #1a237e; }
        .login-container .tab-content { display: none; }
        .login-container .tab-content.active { display: block; }
        
        /* ===== APP ===== */
        #app { display: none; }
        #app.active { display: block; }
        
        /* Header */
        .header { background: linear-gradient(135deg, #1a237e, #283593); color: white; padding: 12px 25px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,0.3); position: sticky; top: 0; z-index: 100; }
        .header h1 { font-size: 1.3em; }
        .header h1 span { font-weight: 300; opacity: 0.8; }
        .header-right { display: flex; align-items: center; gap: 15px; }
        .header-right .user-info { display: flex; align-items: center; gap: 10px; }
        .header-right .user-info .avatar { width: 32px; height: 32px; border-radius: 50%; background: rgba(255,255,255,0.2); display: flex; align-items: center; justify-content: center; font-weight: bold; }
        .header-right .btn-logout { background: rgba(255,255,255,0.15); color: white; border: none; padding: 6px 14px; border-radius: 4px; cursor: pointer; transition: background 0.3s; font-size: 0.9em; }
        .header-right .btn-logout:hover { background: rgba(255,255,255,0.3); }
        .notif-btn { background: transparent; border: none; color: white; font-size: 1.3em; cursor: pointer; position: relative; }
        .notif-badge { position: absolute; top: -8px; right: -8px; background: #e53935; color: white; border-radius: 50%; padding: 1px 6px; font-size: 10px; min-width: 18px; text-align: center; }
        
        /* Container */
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        /* Toolbar */
        .toolbar { background: white; padding: 15px 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 20px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
        .toolbar input, .toolbar select { padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; flex: 1; min-width: 150px; font-size: 14px; }
        .toolbar input:focus, .toolbar select:focus { border-color: #1a237e; outline: none; }
        .toolbar .btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-weight: 500; transition: all 0.3s; font-size: 14px; }
        .toolbar .btn-primary { background: #1a237e; color: white; }
        .toolbar .btn-primary:hover { background: #0d1457; }
        .toolbar .btn-success { background: #2e7d32; color: white; }
        .toolbar .btn-success:hover { background: #1b5e20; }
        .toolbar .btn-info { background: #1565c0; color: white; }
        .toolbar .btn-info:hover { background: #0d47a1; }
        .toolbar .btn-orange { background: #e65100; color: white; }
        .toolbar .btn-orange:hover { background: #bf360c; }
        
        /* Stats Bar */
        .stats-bar { background: white; padding: 12px 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 20px; display: flex; gap: 30px; flex-wrap: wrap; }
        .stats-bar .stat-item { display: flex; align-items: center; gap: 8px; }
        .stats-bar .stat-item .label { color: #666; font-size: 0.9em; }
        .stats-bar .stat-item .value { font-weight: 700; font-size: 1.2em; color: #1a237e; }
        
        /* Grid */
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
        
        /* Card */
        .card { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); transition: transform 0.2s, box-shadow 0.2s; }
        .card:hover { transform: translateY(-3px); box-shadow: 0 4px 16px rgba(0,0,0,0.12); }
        .card .header-card { display: flex; justify-content: space-between; align-items: start; }
        .card .header-card h3 { color: #1a237e; font-size: 1.1em; margin-bottom: 5px; }
        .card .header-card .ref { color: #888; font-size: 0.8em; }
        .card .header-card .version-badge { background: #e3f2fd; color: #0d47a1; padding: 2px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 600; }
        .card .meta { color: #888; font-size: 0.85em; margin: 8px 0; }
        .card .meta i { margin-right: 4px; }
        .card .description { color: #555; font-size: 0.9em; margin: 8px 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .card .tags { display: flex; flex-wrap: wrap; gap: 4px; margin: 8px 0; }
        .card .tags .tag { background: #e3f2fd; color: #0d47a1; padding: 2px 10px; border-radius: 12px; font-size: 0.75em; }
        .card .actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
        .card .actions .btn-sm { padding: 5px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8em; transition: all 0.3s; }
        .card .actions .btn-download { background: #1565c0; color: white; }
        .card .actions .btn-download:hover { background: #0d47a1; }
        .card .actions .btn-version { background: #6a1b9a; color: white; }
        .card .actions .btn-version:hover { background: #4a148c; }
        .card .actions .btn-delete { background: #c62828; color: white; }
        .card .actions .btn-delete:hover { background: #b71c1c; }
        .card .actions .btn-edit { background: #f57f17; color: white; }
        .card .actions .btn-edit:hover { background: #e65100; }
        .card .footer-card { border-top: 1px solid #eee; margin-top: 10px; padding-top: 10px; display: flex; justify-content: space-between; color: #999; font-size: 0.75em; }
        
        /* Empty state */
        .empty { text-align: center; padding: 60px 20px; color: #888; }
        .empty .icon { font-size: 48px; margin-bottom: 16px; }
        
        /* Modal */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); align-items: center; justify-content: center; z-index: 1000; }
        .modal.active { display: flex; }
        .modal-content { background: white; padding: 30px; border-radius: 12px; max-width: 600px; width: 95%; max-height: 90vh; overflow-y: auto; }
        .modal-content h2 { color: #1a237e; margin-bottom: 20px; }
        .modal-content .form-group { margin-bottom: 15px; }
        .modal-content .form-group label { display: block; margin-bottom: 4px; font-weight: 500; color: #555; font-size: 0.9em; }
        .modal-content .form-group input, .modal-content .form-group textarea, .modal-content .form-group select { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        .modal-content .form-group input:focus, .modal-content .form-group textarea:focus, .modal-content .form-group select:focus { border-color: #1a237e; outline: none; }
        .modal-content .form-group textarea { min-height: 60px; resize: vertical; }
        .modal-content .modal-actions { display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }
        .modal-content .modal-actions .btn { padding: 8px 24px; border: none; border-radius: 6px; cursor: pointer; font-weight: 500; }
        .modal-content .modal-actions .btn-primary { background: #1a237e; color: white; }
        .modal-content .modal-actions .btn-primary:hover { background: #0d1457; }
        .modal-content .modal-actions .btn-secondary { background: #666; color: white; }
        .modal-content .modal-actions .btn-secondary:hover { background: #555; }
        
        /* File drop zone */
        .file-upload-area { border: 2px dashed #ddd; padding: 20px; text-align: center; border-radius: 8px; margin: 10px 0; cursor: pointer; transition: all 0.3s; }
        .file-upload-area:hover { border-color: #1a237e; background: #f5f5f5; }
        .file-upload-area.dragover { border-color: #1a237e; background: #e8eaf6; }
        .file-upload-area .file-name { color: #1a237e; font-weight: 500; }
        
        /* Notifications panel */
        .notif-panel { position: fixed; top: 70px; right: 20px; width: 350px; max-height: 500px; overflow-y: auto; background: white; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.2); z-index: 999; display: none; padding: 15px; }
        .notif-panel.active { display: block; }
        .notif-panel .notif-item { padding: 10px; border-bottom: 1px solid #eee; }
        .notif-panel .notif-item:last-child { border-bottom: none; }
        .notif-panel .notif-item .notif-type { font-weight: 600; }
        .notif-panel .notif-item .notif-type.import { color: #2e7d32; }
        .notif-panel .notif-item .notif-type.update { color: #1565c0; }
        .notif-panel .notif-item .notif-type.delete { color: #c62828; }
        .notif-panel .notif-item .notif-date { color: #999; font-size: 0.75em; }
        .notif-panel .notif-empty { text-align: center; color: #888; padding: 20px; }
        .notif-panel .notif-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        
        /* Responsive */
        @media (max-width: 768px) {
            .header { padding: 10px 15px; flex-wrap: wrap; }
            .header h1 { font-size: 1em; }
            .header-right { flex-wrap: wrap; gap: 8px; }
            .toolbar { flex-direction: column; align-items: stretch; }
            .toolbar input, .toolbar select { flex: none; }
            .grid { grid-template-columns: 1fr; }
            .stats-bar { flex-direction: column; gap: 8px; }
            .notif-panel { width: 95%; right: 2.5%; top: 80px; }
            .modal-content { padding: 20px; }
        }
        
        /* Loading spinner */
        .loader { display: inline-block; width: 20px; height: 20px; border: 3px solid #f3f3f3; border-top: 3px solid #1a237e; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        /* Toast */
        .toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 24px; border-radius: 8px; color: white; font-weight: 500; z-index: 2000; animation: slideUp 0.3s ease; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
        .toast.success { background: #2e7d32; }
        .toast.error { background: #c62828; }
        .toast.info { background: #1565c0; }
        @keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    </style>
</head>
<body>

<!-- ===== PAGE DE CONNEXION ===== -->
<div id="loginPage">
    <div class="login-container">
        <h1>📋 Gestionnaire de Fiches</h1>
        <div class="tabs">
            <button class="tab-btn active" data-tab="login">Connexion</button>
            <button class="tab-btn" data-tab="register">Inscription</button>
        </div>
        
        <div id="errorMessage" class="error"></div>
        
        <!-- Tab Connexion -->
        <div id="tab-login" class="tab-content active">
            <form id="loginForm">
                <div class="form-group">
                    <label>Nom d'utilisateur</label>
                    <input type="text" id="loginUsername" placeholder="Votre nom d'utilisateur" required>
                </div>
                <div class="form-group">
                    <label>Mot de passe</label>
                    <input type="password" id="loginPassword" placeholder="Votre mot de passe" required>
                </div>
                <button type="submit" class="btn">Se connecter</button>
            </form>
        </div>
        
        <!-- Tab Inscription -->
        <div id="tab-register" class="tab-content">
            <form id="registerForm">
                <div class="form-group">
                    <label>Nom d'utilisateur</label>
                    <input type="text" id="regUsername" placeholder="Choisissez un nom" required>
                </div>
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" id="regEmail" placeholder="votre@email.com" required>
                </div>
                <div class="form-group">
                    <label>Mot de passe</label>
                    <input type="password" id="regPassword" placeholder="Minimum 6 caractères" required minlength="6">
                </div>
                <button type="submit" class="btn">S'inscrire</button>
            </form>
        </div>
    </div>
</div>

<!-- ===== APPLICATION ===== -->
<div id="app">
    <!-- Header -->
    <div class="header">
        <h1>📋 Gestionnaire <span>de Fiches Techniques</span></h1>
        <div class="header-right">
            <div class="user-info">
                <div class="avatar" id="userAvatar">U</div>
                <span id="userName">Utilisateur</span>
            </div>
            <button class="notif-btn" onclick="toggleNotifications()">
                🔔
                <span class="notif-badge" id="notifCount">0</span>
            </button>
            <button class="btn-logout" onclick="logout()">Déconnexion</button>
        </div>
    </div>
    
    <!-- Panneau de notifications -->
    <div class="notif-panel" id="notifPanel">
        <div class="notif-header">
            <strong>Notifications</strong>
            <button onclick="markAllRead()" style="background:none;border:none;color:#1a237e;cursor:pointer;">Tout marquer lu</button>
        </div>
        <div id="notifList">
            <div class="notif-empty">Aucune notification</div>
        </div>
    </div>
    
    <div class="container">
        <!-- Statistiques -->
        <div class="stats-bar" id="statsBar">
            <div class="stat-item"><span class="label">📄 Total :</span><span class="value" id="statTotal">0</span></div>
            <div class="stat-item"><span class="label">📂 Catégories :</span><span class="value" id="statCategories">0</span></div>
            <div class="stat-item"><span class="label">🏷️ Tags :</span><span class="value" id="statTags">0</span></div>
        </div>
        
        <!-- Toolbar -->
        <div class="toolbar">
            <input type="text" id="searchInput" placeholder="🔍 Rechercher (nom, référence, fabricant...)" style="flex:2;">
            <select id="categorieFilter">
                <option value="">Toutes catégories</option>
            </select>
            <select id="tagFilter">
                <option value="">Tous tags</option>
            </select>
            <button class="btn btn-primary" onclick="loadFiches()">🔄</button>
            <button class="btn btn-success" onclick="openImportModal()">📤 Importer</button>
            <button class="btn btn-info" onclick="exportCSV()">📊 CSV</button>
            <button class="btn btn-orange" onclick="exportExcel()">📊 Excel</button>
        </div>
        
        <!-- Grille des fiches -->
        <div id="fichesGrid" class="grid">
            <div class="empty"><div class="icon">⏳</div>Chargement...</div>
        </div>
    </div>
</div>

<!-- ===== MODAL IMPORT ===== -->
<div id="importModal" class="modal">
    <div class="modal-content">
        <h2>📤 Importer une fiche technique</h2>
        <form id="importForm" enctype="multipart/form-data">
            <div class="form-group">
                <label>Fichier *</label>
                <div class="file-upload-area" id="fileDropZone">
                    <p>📁 Glissez-déposez ou cliquez pour sélectionner</p>
                    <input type="file" id="fileInput" name="fichier" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.jpg,.png" style="display:none;">
                </div>
            </div>
            <div class="form-group">
                <label>Référence *</label>
                <input type="text" id="refInput" name="reference" placeholder="ex: FT-2026-001">
            </div>
            <div class="form-group">
                <label>Nom *</label>
                <input type="text" id="nomInput" name="nom" placeholder="Nom de la fiche">
            </div>
            <div class="form-group">
                <label>Description</label>
                <textarea id="descInput" name="description" placeholder="Description du produit/composant"></textarea>
            </div>
            <div class="form-group">
                <label>Catégorie</label>
                <select id="categorieInput" name="categorie">
                    <option value="">Non catégorisé</option>
                    <option value="Électronique">Électronique</option>
                    <option value="Mécanique">Mécanique</option>
                    <option value="Logiciel">Logiciel</option>
                    <option value="Matériaux">Matériaux</option>
                    <option value="Électrique">Électrique</option>
                    <option value="Autre">Autre</option>
                </select>
            </div>
            <div class="form-group">
                <label>Fabricant</label>
                <input type="text" id="fabricantInput" name="fabricant" placeholder="Nom du fabricant">
            </div>
            <div class="form-group">
                <label>Version</label>
                <input type="text" id="versionInput" name="version" placeholder="1.0" value="1.0">
            </div>
            <div class="form-group">
                <label>Tags (séparés par des virgules)</label>
                <input type="text" id="tagsInput" name="tags" placeholder="ex: composant, certification, résistance">
            </div>
            <div class="modal-actions">
                <button type="submit" class="btn btn-primary">Importer</button>
                <button type="button" class="btn btn-secondary" onclick="closeImportModal()">Annuler</button>
            </div>
        </form>
    </div>
</div>

<!-- ===== MODAL VERSION ===== -->
<div id="versionModal" class="modal">
    <div class="modal-content">
        <h2>📌 Ajouter une version</h2>
        <form id="versionForm" enctype="multipart/form-data">
            <input type="hidden" id="versionFicheId" name="fiche_id">
            <div class="form-group">
                <label>Nouveau fichier *</label>
                <div class="file-upload-area" id="versionDropZone">
                    <p>📁 Cliquez pour sélectionner</p>
                    <input type="file" id="versionFileInput" name="fichier" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt" style="display:none;">
                </div>
            </div>
            <div class="form-group">
                <label>Commentaire</label>
                <textarea id="versionComment" name="commentaire" placeholder="Description des changements"></textarea>
            </div>
            <div class="modal-actions">
                <button type="submit" class="btn btn-primary">Ajouter la version</button>
                <button type="button" class="btn btn-secondary" onclick="closeVersionModal()">Annuler</button>
            </div>
        </form>
    </div>
</div>

<!-- ===== MODAL HISTORIQUE ===== -->
<div id="historyModal" class="modal">
    <div class="modal-content">
        <h2>📜 Historique des versions</h2>
        <div id="historyList">
            <div class="empty">Aucune version</div>
        </div>
        <div class="modal-actions">
            <button type="button" class="btn btn-secondary" onclick="closeHistoryModal()">Fermer</button>
        </div>
    </div>
</div>

<!-- ===== MODAL EDITION ===== -->
<div id="editModal" class="modal">
    <div class="modal-content">
        <h2>✏️ Modifier la fiche</h2>
        <form id="editForm">
            <input type="hidden" id="editFicheId">
            <div class="form-group">
                <label>Nom</label>
                <input type="text" id="editNom" required>
            </div>
            <div class="form-group">
                <label>Description</label>
                <textarea id="editDescription"></textarea>
            </div>
            <div class="form-group">
                <label>Catégorie</label>
                <select id="editCategorie">
                    <option value="">Non catégorisé</option>
                    <option value="Électronique">Électronique</option>
                    <option value="Mécanique">Mécanique</option>
                    <option value="Logiciel">Logiciel</option>
                    <option value="Matériaux">Matériaux</option>
                    <option value="Électrique">Électrique</option>
                    <option value="Autre">Autre</option>
                </select>
            </div>
            <div class="form-group">
                <label>Fabricant</label>
                <input type="text" id="editFabricant">
            </div>
            <div class="form-group">
                <label>Tags (séparés par des virgules)</label>
                <input type="text" id="editTags" placeholder="ex: composant, certification">
            </div>
            <div class="modal-actions">
                <button type="submit" class="btn btn-primary">Enregistrer</button>
                <button type="button" class="btn btn-secondary" onclick="closeEditModal()">Annuler</button>
            </div>
        </form>
    </div>
</div>

<!-- ===== SCRIPTS ===== -->
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js" crossorigin="anonymous"></script>
<script>
// =================================================================================
// VARIABLES GLOBALES
// =================================================================================

let token = localStorage.getItem('token');
let currentUser = JSON.parse(localStorage.getItem('user') || 'null');
let socket = null;
let notificationInterval = null;

// =================================================================================
// AUTHENTIFICATION
// =================================================================================

// Gestion des onglets
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        this.classList.add('active');
        document.getElementById('tab-' + this.dataset.tab).classList.add('active');
    });
});

// Login
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.style.display = 'none';
    
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        if (!response.ok) {
            errorDiv.textContent = data.error || 'Erreur de connexion';
            errorDiv.style.display = 'block';
            return;
        }
        
        token = data.token;
        currentUser = data.user;
        localStorage.setItem('token', token);
        localStorage.setItem('user', JSON.stringify(currentUser));
        
        // Passer à l'application
        document.getElementById('loginPage').style.display = 'none';
        document.getElementById('app').classList.add('active');
        document.getElementById('userName').textContent = currentUser.username;
        document.getElementById('userAvatar').textContent = currentUser.username.charAt(0).toUpperCase();
        
        initApp();
    } catch (error) {
        errorDiv.textContent = 'Erreur réseau';
        errorDiv.style.display = 'block';
    }
});

// Register
document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.style.display = 'none';
    
    const username = document.getElementById('regUsername').value;
    const email = document.getElementById('regEmail').value;
    const password = document.getElementById('regPassword').value;
    
    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password })
        });
        
        const data = await response.json();
        if (!response.ok) {
            errorDiv.textContent = data.error || "Erreur d'inscription";
            errorDiv.style.display = 'block';
            return;
        }
        
        toast('Inscription réussie ! Vous pouvez vous connecter.', 'success');
        // Passer à l'onglet login
        document.querySelectorAll('.tab-btn')[0].click();
        document.getElementById('loginUsername').value = username;
        document.getElementById('loginPassword').value = '';
    } catch (error) {
        errorDiv.textContent = 'Erreur réseau';
        errorDiv.style.display = 'block';
    }
});

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    token = null;
    currentUser = null;
    document.getElementById('app').classList.remove('active');
    document.getElementById('loginPage').style.display = 'flex';
    if (socket) { socket.disconnect(); socket = null; }
    if (notificationInterval) { clearInterval(notificationInterval); }
}

// Vérifier si déjà connecté
if (token && currentUser) {
    document.getElementById('loginPage').style.display = 'none';
    document.getElementById('app').classList.add('active');
    document.getElementById('userName').textContent = currentUser.username;
    document.getElementById('userAvatar').textContent = currentUser.username.charAt(0).toUpperCase();
    initApp();
}

// =================================================================================
// INITIALISATION
// =================================================================================

function initApp() {
    // WebSocket pour les notifications
    connectSocket();
    // Chargement initial
    loadFiches();
    loadStats();
    loadCategories();
    loadTags();
    // Intervalle de rafraîchissement des notifications
    if (notificationInterval) clearInterval(notificationInterval);
    notificationInterval = setInterval(loadNotifications, 30000);
}

// =================================================================================
// WEBSOCKET
// =================================================================================

function connectSocket() {
    if (socket) socket.disconnect();
    socket = io('', { query: { token: token } });
    
    socket.on('connect', () => {
        console.log('WebSocket connecté');
        socket.emit('subscribe', {});
    });
    
    socket.on('notification', (data) => {
        loadNotifications();
        toast(data.message, 'info');
    });
    
    socket.on('disconnect', () => {
        console.log('WebSocket déconnecté');
    });
}

// =================================================================================
// NOTIFICATIONS
// =================================================================================

async function loadNotifications() {
    if (!token) return;
    try {
        const response = await fetch('/api/notifications', {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        const data = await response.json();
        document.getElementById('notifCount').textContent = data.length;
        
        const list = document.getElementById('notifList');
        if (data.length === 0) {
            list.innerHTML = '<div class="notif-empty">✅ Aucune notification</div>';
            return;
        }
        
        list.innerHTML = data.map(n => {
            const icon = n.type === 'import' ? '📤' : n.type === 'update' ? '📝' : '🗑️';
            return '<div class="notif-item">'
                + '<div>'
                + '<span class="notif-type ' + n.type + '">' + icon + ' ' + n.type + '</span>'
                + '<span class="notif-date">' + n.created_at + '</span>'
                + '</div>'
                + '<div>' + n.message + '</div>'
                + '</div>';
        }).join('');
    } catch (e) {}
}

function toggleNotifications() {
    const panel = document.getElementById('notifPanel');
    panel.classList.toggle('active');
    if (panel.classList.contains('active')) {
        loadNotifications();
    }
}

async function markAllRead() {
    try {
        await fetch('/api/notifications/read-all', {
            method: 'PUT',
            headers: { 'Authorization': 'Bearer ' + token }
        });
        loadNotifications();
    } catch (e) {}
}

// =================================================================================
// FICHES - CHARGEMENT
// =================================================================================

async function loadFiches() {
    const search = document.getElementById('searchInput').value;
    const categorie = document.getElementById('categorieFilter').value;
    const tag = document.getElementById('tagFilter').value;
    
    let url = '/api/fiches?';
    if (search) url += 'search=' + encodeURIComponent(search) + '&';
    if (categorie) url += 'categorie=' + encodeURIComponent(categorie) + '&';
    if (tag) url += 'tag=' + encodeURIComponent(tag) + '&';
    
    try {
        const response = await fetch(url, {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        const fiches = await response.json();
        renderFiches(fiches);
    } catch (error) {
        document.getElementById('fichesGrid').innerHTML = '<div class="empty"><div class="icon">❌</div>Erreur de chargement</div>';
    }
}

function renderFiches(fiches) {
    const grid = document.getElementById('fichesGrid');
    if (!fiches || fiches.length === 0) {
        grid.innerHTML = '<div class="empty"><div class="icon">📭</div>Aucune fiche trouvée</div>';
        return;
    }
    
    grid.innerHTML = fiches.map(f => {
        let tagsHtml = '';
        if (f.tags) {
            tagsHtml = f.tags.map(t => '<span class="tag">#' + t + '</span>').join('');
        }
        let historyButton = '';
        if (f.nb_versions > 0) {
            historyButton = '<button class="btn-sm btn-version" onclick="showHistory(' + f.id + ')">📜 ' + f.nb_versions + '</button>';
        }
        return '<div class="card">'
            + '<div class="header-card">'
            + '<div>'
            + '<h3>' + f.nom + '</h3>'
            + '<div class="ref">📌 ' + f.reference + '</div>'
            + '</div>'
            + '<span class="version-badge">v' + f.version_actuelle + '</span>'
            + '</div>'
            + '<div class="meta">🏷️ ' + (f.categorie || 'Non catégorisé') + ' | ' + (f.fabricant || 'Fabricant inconnu') + '</div>'
            + (f.description ? '<div class="description">' + f.description + '</div>' : '')
            + '<div class="tags">' + tagsHtml + '</div>'
            + '<div class="actions">'
            + '<button class="btn-sm btn-download" onclick="downloadFiche(' + f.id + ')">⬇️ Télécharger</button>'
            + '<button class="btn-sm btn-version" onclick="openVersionModal(' + f.id + ')">📌 Version</button>'
            + '<button class="btn-sm btn-edit" onclick="openEditModal(' + f.id + ')">✏️</button>'
            + historyButton
            + '<button class="btn-sm btn-delete" onclick="deleteFiche(' + f.id + ')">🗑️</button>'
            + '</div>'
            + '<div class="footer-card">'
            + '<span>👤 ' + (f.auteur || 'Inconnu') + '</span>'
            + '<span>📅 ' + f.date_import + '</span>'
            + '</div>'
            + '</div>';
    }).join('');
}

// =================================================================================
// FICHES - ACTIONS
// =================================================================================

async function downloadFiche(id) {
    window.location.href = '/api/fiches/' + id + '/download?token=' + token;
}

async function deleteFiche(id) {
    if (!confirm('Supprimer cette fiche définitivement ?')) return;
    try {
        await fetch('/api/fiches/' + id, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        });
        toast('Fiche supprimée', 'success');
        loadFiches();
        loadStats();
    } catch (e) {
        toast('Erreur lors de la suppression', 'error');
    }
}

// =================================================================================
// FICHES - IMPORT
// =================================================================================

function openImportModal() {
    document.getElementById('importModal').classList.add('active');
    document.getElementById('importForm').reset();
    document.querySelector('#fileDropZone p').innerHTML = '📁 Glissez-déposez ou cliquez pour sélectionner';
}

function closeImportModal() {
    document.getElementById('importModal').classList.remove('active');
}

// Drag & drop import
const dropZone = document.getElementById('fileDropZone');
dropZone.addEventListener('click', () => document.getElementById('fileInput').click());
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        document.getElementById('fileInput').files = files;
        document.querySelector('#fileDropZone p').innerHTML = '📄 ' + files[0].name;
    }
});
document.getElementById('fileInput').addEventListener('change', function() {
    if (this.files.length > 0) {
        document.querySelector('#fileDropZone p').innerHTML = '📄 ' + this.files[0].name;
    }
});

document.getElementById('importForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData();
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files || fileInput.files.length === 0) {
        toast('Veuillez sélectionner un fichier', 'error');
        return;
    }
    
    formData.append('fichier', fileInput.files[0]);
    formData.append('reference', document.getElementById('refInput').value);
    formData.append('nom', document.getElementById('nomInput').value);
    formData.append('description', document.getElementById('descInput').value);
    formData.append('categorie', document.getElementById('categorieInput').value);
    formData.append('fabricant', document.getElementById('fabricantInput').value);
    formData.append('version', document.getElementById('versionInput').value);
    formData.append('tags', document.getElementById('tagsInput').value);
    
    try {
        const response = await fetch('/api/fiches', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + token },
            body: formData
        });
        const data = await response.json();
        if (!response.ok) {
            toast(data.error || "Erreur d'import", 'error');
            return;
        }
        closeImportModal();
        toast('Fiche importée avec succès !', 'success');
        loadFiches();
        loadStats();
        loadTags();
    } catch (e) {
        toast('Erreur réseau', 'error');
    }
});

// =================================================================================
// FICHES - VERSION
// =================================================================================

function openVersionModal(ficheId) {
    document.getElementById('versionFicheId').value = ficheId;
    document.getElementById('versionModal').classList.add('active');
    document.getElementById('versionForm').reset();
    document.querySelector('#versionDropZone p').innerHTML = '📁 Cliquez pour sélectionner';
}

function closeVersionModal() {
    document.getElementById('versionModal').classList.remove('active');
}

// Drag & drop version
const versionDrop = document.getElementById('versionDropZone');
versionDrop.addEventListener('click', () => document.getElementById('versionFileInput').click());
versionDrop.addEventListener('dragover', (e) => { e.preventDefault(); versionDrop.classList.add('dragover'); });
versionDrop.addEventListener('dragleave', () => versionDrop.classList.remove('dragover'));
versionDrop.addEventListener('drop', (e) => {
    e.preventDefault();
    versionDrop.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        document.getElementById('versionFileInput').files = files;
        document.querySelector('#versionDropZone p').innerHTML = '📄 ' + files[0].name;
    }
});
document.getElementById('versionFileInput').addEventListener('change', function() {
    if (this.files.length > 0) {
        document.querySelector('#versionDropZone p').innerHTML = '📄 ' + this.files[0].name;
    }
});

document.getElementById('versionForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const ficheId = document.getElementById('versionFicheId').value;
    const formData = new FormData();
    const fileInput = document.getElementById('versionFileInput');
    if (!fileInput.files || fileInput.files.length === 0) {
        toast('Veuillez sélectionner un fichier', 'error');
        return;
    }
    
    formData.append('fichier', fileInput.files[0]);
    formData.append('commentaire', document.getElementById('versionComment').value);
    
    try {
        const response = await fetch('/api/fiches/' + ficheId + '/version', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + token },
            body: formData
        });
        const data = await response.json();
        if (!response.ok) {
            toast(data.error || 'Erreur', 'error');
            return;
        }
        closeVersionModal();
        toast('Version ajoutée avec succès !', 'success');
        loadFiches();
    } catch (e) {
        toast('Erreur réseau', 'error');
    }
});

// =================================================================================
// FICHES - HISTORIQUE
// =================================================================================

async function showHistory(ficheId) {
    try {
        const response = await fetch('/api/fiches/' + ficheId, {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        const data = await response.json();
        const list = document.getElementById('historyList');
        
        if (!data.historique || data.historique.length === 0) {
            list.innerHTML = '<div class="empty">Aucune version</div>';
        } else {
            list.innerHTML = data.historique.map(v => {
                return '<div style="padding:10px;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center;">'
                    + '<div>'
                    + '<strong>Version ' + v.version + '</strong>'
                    + '<div style="color:#888;font-size:0.85em;">' + (v.commentaire || 'Aucun commentaire') + '</div>'
                    + '<div style="color:#999;font-size:0.75em;">' + v.date + ' - ' + (v.auteur || 'Inconnu') + '</div>'
                    + '</div>'
                    + '<a href="/api/fiches/' + ficheId + '/versions/' + v.id + '/download?token=' + token + '" target="_blank" style="background:#1565c0;color:white;padding:4px 12px;border-radius:4px;text-decoration:none;font-size:0.8em;">⬇️</a>'
                    + '</div>';
            }).join('');
        }
        document.getElementById('historyModal').classList.add('active');
    } catch (e) {
        toast('Erreur de chargement', 'error');
    }
}

function closeHistoryModal() {
    document.getElementById('historyModal').classList.remove('active');
}

// =================================================================================
// FICHES - EDITION
// =================================================================================

async function openEditModal(ficheId) {
    try {
        const response = await fetch('/api/fiches/' + ficheId, {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        const data = await response.json();
        
        document.getElementById('editFicheId').value = ficheId;
        document.getElementById('editNom').value = data.nom || '';
        document.getElementById('editDescription').value = data.description || '';
        document.getElementById('editCategorie').value = data.categorie || '';
        document.getElementById('editFabricant').value = data.fabricant || '';
        document.getElementById('editTags').value = data.tags ? data.tags.join(', ') : '';
        
        document.getElementById('editModal').classList.add('active');
    } catch (e) {
        toast('Erreur de chargement', 'error');
    }
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
}

document.getElementById('editForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const id = document.getElementById('editFicheId').value;
    const data = {
        nom: document.getElementById('editNom').value,
        description: document.getElementById('editDescription').value,
        categorie: document.getElementById('editCategorie').value,
        fabricant: document.getElementById('editFabricant').value,
        tags: document.getElementById('editTags').value.split(',').map(t => t.trim()).filter(t => t)
    };
    
    try {
        const response = await fetch('/api/fiches/' + id, {
            method: 'PUT',
            headers: {
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (!response.ok) {
            toast(result.error || 'Erreur', 'error');
            return;
        }
        closeEditModal();
        toast('Fiche mise à jour', 'success');
        loadFiches();
    } catch (e) {
        toast('Erreur réseau', 'error');
    }
});

// =================================================================================
// STATISTIQUES
// =================================================================================

async function loadStats() {
    try {
        const response = await fetch('/api/stats', {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        const data = await response.json();
        document.getElementById('statTotal').textContent = data.total_fiches || 0;
        document.getElementById('statCategories').textContent = data.categories ? data.categories.filter(c => c.nom !== 'Non catégorisé').length : 0;
    } catch (e) {}
}

// =================================================================================
// FILTRES
// =================================================================================

async function loadCategories() {
    try {
        const response = await fetch('/api/fiches?', {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        const fiches = await response.json();
        const categories = [...new Set(fiches.map(f => f.categorie).filter(c => c))];
        const select = document.getElementById('categorieFilter');
        categories.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            select.appendChild(opt);
        });
    } catch (e) {}
}

async function loadTags() {
    try {
        const response = await fetch('/api/tags', {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        const tags = await response.json();
        const select = document.getElementById('tagFilter');
        select.innerHTML = '<option value="">Tous tags</option>';
        tags.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.nom;
            opt.textContent = t.nom;
            select.appendChild(opt);
        });
        document.getElementById('statTags').textContent = tags.length;
    } catch (e) {}
}

// =================================================================================
// EXPORT
// =================================================================================

function exportCSV() {
    window.location.href = '/api/export/csv?token=' + token;
}

function exportExcel() {
    window.location.href = '/api/export/excel?token=' + token;
}

// =================================================================================
// TOAST
// =================================================================================

function toast(message, type = 'info') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.5s';
        setTimeout(() => toast.remove(), 500);
    }, 4000);
}

// =================================================================================
// RECHERCHE EN TEMPS RÉEL
// =================================================================================

document.getElementById('searchInput').addEventListener('input', loadFiches);
document.getElementById('categorieFilter').addEventListener('change', loadFiches);
document.getElementById('tagFilter').addEventListener('change', loadFiches);

// =================================================================================
// FERMETURE DES MODALS PAR CLIC EXTERNE
// =================================================================================

document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', function(e) {
        if (e.target === this) {
            this.classList.remove('active');
        }
    });
});

// =================================================================================
// RACCOURCI CLAVIER
// =================================================================================

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(m => m.classList.remove('active'));
        document.getElementById('notifPanel').classList.remove('active');
    }
    if (e.ctrlKey && e.key === 'f') {
        e.preventDefault();
        document.getElementById('searchInput').focus();
    }
});

console.log('🚀 Gestionnaire de Fiches Techniques - Version Complète');
console.log('📋 Fonctionnalités : CRUD, Auth, Search, Export, Versioning, Tags, Notifications');
</script>
</body>
</html>
'''

# =================================================================================
# ROUTE PRINCIPALE
# =================================================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# =================================================================================
# LANCEMENT
# =================================================================================

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 GESTIONNAIRE DE FICHES TECHNIQUES - VERSION COMPLÈTE")
    print("="*80)
    print("📋 Fonctionnalités :")
    print("   ✅ CRUD complet des fiches")
    print("   ✅ Authentification JWT")
    print("   ✅ Recherche avancée (Elasticsearch + SQL)")
    print("   ✅ Export CSV et Excel")
    print("   ✅ Versioning des fichiers")
    print("   ✅ Système de tags")
    print("   ✅ Notifications en temps réel")
    print("   ✅ Statistiques")
    print("   ✅ Interface web moderne")
    print("="*80)
    print("🌐 http://localhost:5000")
    print("👤 Compte par défaut : admin / admin (à créer à l'inscription)")
    print("="*80 + "\n")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)