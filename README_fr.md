# VateCon — AI Support Agent

> Système d'automatisation du support client basé sur l'IA .

---

## Présentation

VateCon AI Support Agent est un système complet qui permet à une entreprise d'automatiser 70 à 80 % de ses tickets de support client grâce à l'IA. L'agent répond en temps réel, cite ses sources, indique son niveau de confiance, et escalade automatiquement les cas complexes vers un humain.

**Stack technique :**
- **Backend** : FastAPI + LangChain + OpenAI GPT-4o + ChromaDB (RAG) + PostgreSQL
- **Frontend** : React + TypeScript + Tailwind CSS + WebSocket
- **Infrastructure** : Docker Compose (4 services orchestrés)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Client (React)                    │
│   /           → Interface de chat temps réel        │
│   /admin      → Dashboard admin + analytics         │
│   /knowledge  → Upload docs + FAQ builder           │
└────────────────────────┬────────────────────────────┘
                         │ HTTP + WebSocket (Nginx proxy)
┌────────────────────────▼────────────────────────────┐
│                 Backend (FastAPI)                   │
│                                                     │
│  WebSocket /ws/chat/{session_id}                    │
│       ↓                                             │
│  SupportAgent (LangChain)                           │
│       ↓                                             │
│  ChromaDB (vectorstore RAG)  ←  docs / FAQ          │
│       ↓                                             │
│  GPT-4o → réponse + score de confiance              │
│       ↓                                             │
│  PostgreSQL (historique conversations)              │
└─────────────────────────────────────────────────────┘
```

---

## Démarrage rapide

### Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé et lancé
- Une clé API OpenAI

### 1. Configurer l'environnement

```bash
cp .env.example .env
```

Ouvrir `.env` et renseigner la clé OpenAI :

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. Lancer le projet

```bash
docker compose up --build
```

Premier démarrage : environ 3-5 minutes (téléchargement des images et installation des dépendances).

### 3. Accéder à l'application

| Interface | URL |
|---|---|
| Chat client | http://localhost:3000 |
| Dashboard admin | http://localhost:3000/admin |
| Knowledge Base | http://localhost:3000/knowledge |
| Documentation API | http://localhost:8000/docs |

---

## Fonctionnalités

### Interface de chat (`/`)

- Connexion WebSocket en temps réel
- Indicateur de frappe pendant que l'IA génère la réponse
- Affichage du **score de confiance** sur chaque réponse (0–100 %)
- Sources citées (nom du document utilisé pour répondre)
- Bannière d'escalade visible quand la conversation est transférée à un humain

### Dashboard admin (`/admin`)

- Statistiques globales : nombre de conversations, taux de résolution IA, escalades, conversations du jour
- Graphique de répartition (résolues par IA / escaladées / clôturées)
- Liste des conversations avec filtres par statut (active, escalated, resolved)
- Visualisation complète des messages d'une conversation
- Bouton de clôture manuelle d'une conversation

### Knowledge Base (`/knowledge`)

**Upload de documents**
Déposer un fichier PDF ou TXT. Le système le découpe automatiquement en chunks, génère les embeddings via OpenAI et les indexe dans ChromaDB. L'agent utilise ensuite ces informations pour répondre aux clients.

**FAQ Builder**
Ajouter directement des paires Question / Réponse sans passer par un fichier. Idéal pour les réponses standard (tarifs, politique de remboursement, horaires...).

### Escalade automatique

L'agent escalade automatiquement une conversation dans deux cas :
1. **Score de confiance < 50 %** — la réponse n'est pas assez fiable
2. **Mot-clé sensible détecté** — remboursement, fraude, parler à un humain, etc.

---

```bash
# Prérequis pour les notebooks de test
pip install requests websocket-client colorama
```

---

## Variables d'environnement

| Variable | Description | Défaut |
|---|---|---|
| `OPENAI_API_KEY` | Clé API OpenAI | — |
| `OPENAI_MODEL` | Modèle utilisé | `gpt-4o` |
| `POSTGRES_USER` | Utilisateur PostgreSQL | `vatecon` |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL | `vatecon_secret` |
| `POSTGRES_DB` | Nom de la base de données | `vatecon_db` |
| `SECRET_KEY` | Clé secrète applicative | — |
| `ALLOWED_ORIGINS` | Origines CORS autorisées | `http://localhost:3000` |

---

## Pitch commercial

| Problème | Solution |
|---|---|
| Une équipe support répond aux mêmes questions 50x par jour | L'agent IA répond à 70–80 % des tickets automatiquement |
| Former un chatbot prend des mois | Déposer ses docs suffit — opérationnel en minutes |
| Les réponses incorrectes nuisent à la réputation | Score de confiance + escalade automatique vers un humain |
| Pas de visibilité sur le support | Dashboard temps réel avec toutes les conversations |

**ROI typique pour une PME :** 5 à 15 heures économisées par semaine sur le support client.
