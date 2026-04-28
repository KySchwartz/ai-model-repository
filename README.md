# ModelHubAI

ModelHubAI is an AI Model Hosting and Repository Suite developed by the Capstone Crew. The platform is a web-based, micro-services platform designed for secure hosting and automated management of AI models. It acts as a central hub bridging model developers and end-users through a "single-point connection" architecture.

**How it works:** Developers upload Python code as a `.zip` or Python file, configure their desired interface, and the system automatically serves the interface and runs the service. The developer only needs to create the AI model—the platform handles deployment to end users.

## Key Components

- **Django Backend** — Manages user authentication, the model catalog, and persistent data storage
- **PostgreSQL Database** — Stores user data, model metadata, and execution metrics
- **FastAPI AI Suite** — Handles model preparation, dependency parsing, and manages sibling containers for execution
- **Secure Sandbox** — An isolated Docker-based Python runtime environment for running untrusted user code

---

## Getting Started with Docker

### Prerequisites

Before starting, install the following software:

- [Git](https://git-scm.com/)
- [VS Code](https://code.visualstudio.com/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  - **Important:** After installation, ensure Docker Desktop is open and running

### Step 1: Clone the Repository

Open your terminal (PowerShell or Command Prompt) and run:

```bash
git clone https://github.com/KySchwartz/ai-model-repository.git
cd ai-model-repository
```

### Step 2: Start the Platform

In your terminal, inside the project folder, run:

```bash
docker compose up --build
```

**What this does:** Automatically downloads PostgreSQL, sets up the Django backend, and prepares the FastAPI AI suite.

**Success indicator:** You will see a line that says `backend-1 | Watching for file changes` or a similar success message.

### Step 3: Set Up the Database (Migrations)

While Docker is running in your first terminal, open a second terminal window and run:

```bash
docker compose exec backend python manage.py makemigrations

docker compose exec backend python manage.py migrate
```

**Important Note!:** These commands update the database and will need to be ran whenever 'models.py' is edited. Failure to do so will result in errors when the system tries to access data not found in the database.

### Step 4: Create an Admin Account

To access the admin panel, create a superuser account:

```bash
docker compose exec backend python manage.py createsuperuser
```

### Step 5: Verify the Setup

Open your browser and verify these three endpoints:

1. **The Website:** http://localhost:8000 (You should see a Rocket Ship landing page)
2. **The AI Service:** http://localhost:8001 (You should see `{"message": "AI Suite is Online"}`)
3. **The Admin Panel:** http://localhost:8000/admin (Log in with the credentials you created)

### Beginner Tips

- Don't install Python or PostgreSQL on your computer—Docker handles that inside containers
- If you get an error about `context "compose" not found`, run: `docker context use default`
- Keep the terminal running Docker open while you work
- You need to open the Docker Desktop application to start the Docker Engine before running `Docker compose up`

---

## Managing the Application

### Stopping the Application

When you're finished working on the project, follow these steps:

1. **Stop the Services** — Press `Ctrl + C` in the terminal running Docker
   - This sends an interrupt signal to the containers
   - You'll see lines like `Gracefully stopping...`
   - Wait until you see your regular command prompt

2. **Clean Up (Optional but Recommended)** — Run:
   ```bash
   docker compose down
   ```
   - `Ctrl + C` stops containers, but `down` removes them from active memory
   - Your data is safely stored in volumes and will persist
   - This command can be used in any terminal within the project folder to stop the application

3. **Close Docker Desktop** — After the system has been shut down, you may close the Docker Desktop application

### Restarting the Application

When you return to the project, follow this sequence:

1. **Start Docker Desktop** — Wait 30–60 seconds for the engine to fully start

2. **Navigate to Your Project** — Open your terminal and navigate to the project folder:
   ```bash
   cd ai-model-repository
   ```
   Alternatively, the user can open the project folder in VSCode and select Terminal -> New Terminal

3. **Bring the System Online** — Run:
   ```bash
   docker compose up
   ```
   - **Note:** You only need the `--build` flag if you've added new Python libraries to `requirements.txt`, made edits to the `docker-compose.yml` file, or edited a `Dockerfile`.
   - Edits to most `.py` files can be accomplished by using `docker compose down` and then re-running `docker compose up`.
   - Your database and admin account will persist from your previous session.

4. **Verify** — Check http://localhost:8000 in your browser

### Pro Tip: Detached Mode

If you don't want to see logs scrolling and want to reuse the terminal, run:

```bash
docker compose up -d
```

The `-d` flag runs servers in the background. Stop them later with:

```bash
docker compose stop
```
or 
```bash
docker compose down
```

- This is only recommended when running the system so that a single terminal can be used. When working on the application it may be necessary to see the debug logs that are sent to the terminal from every container when using `Docker compose up`.

- Logs and Debug messages can also be viewed within the Docker Desktop interface within their respective containers.

**A Final Note** - The Sandbox container will appear as a randomly generated Docker name when an AI agent is running. This is both for security and because the Sandbox is a temporary sibling container of the ai_suite created using the Python Docker SDK command `client.containers.run` defined in `ai_suite/routes/execute.py`.