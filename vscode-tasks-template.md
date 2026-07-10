<!-- # ${workspaceFolder}\\.vscode\\tasks.json  -->
<!-- Setup:  Run Task: 'Dev: initialize environment' -->
<!-- Launch: Run task: 'Dev: Start frontend and backend' -->
<!-- NB: if bash is default shell, then edit paths => '.replace("\\", "/")' -->

{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Backend: create venv",
      "type": "shell",
      "command": "python",
      "args": [
        "-m",
        "venv",
        ".venv"
      ],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "presentation": {
        "reveal": "always",
        "panel": "dedicated",
        "group": "setup"
      },
      "problemMatcher": []
    },
    {
      "label": "Backend: install requirements",
      "type": "shell",
      "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "pip",
        "install",
        "--upgrade",
        "pip",
        "-r",
        "requirements.txt"
      ],
      "options": {
        "cwd": "${workspaceFolder}/backend"
      },
      "dependsOn": [
        "Backend: create venv"
      ],
      "dependsOrder": "sequence",
      "presentation": {
        "reveal": "always",
        "panel": "dedicated",
        "group": "setup"
      },
      "problemMatcher": []
    },
    {
      "label": "Frontend: install packages",
      "type": "shell",
      "command": "npm",
      "args": [
        "install"
      ],
      "options": {
        "cwd": "${workspaceFolder}\\frontend"
      },
      "presentation": {
        "reveal": "always",
        "panel": "dedicated",
        "group": "setup"
      },
      "problemMatcher": []
    },
    {
      "label": "Dev: initialize environment",
      "dependsOn": [
        "Backend: install requirements",
        "Frontend: install packages"
      ],
      "dependsOrder": "parallel",
      "problemMatcher": []
    },
    {
      "label": "Backend: FastAPI",
      "type": "shell",
      "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "uvicorn",
        "app.main:app",
        "--reload",
      ],
      "options": {
        "cwd": "${workspaceFolder}\\backend"
      },
      "presentation": {
        "reveal": "always",
        "panel": "dedicated",
        "group": "dev"
      },
      "problemMatcher": []
    },
    {
      "label": "Frontend: Vue",
      "type": "shell",
      "command": "npm",
      "args": [
        "run",
        "dev",
      ],
      "options": {
        "cwd": "${workspaceFolder}\\frontend"
      },
      "presentation": {
        "reveal": "always",
        "panel": "dedicated",
        "group": "dev"
      },
      "problemMatcher": []
    },
    {
      "label": "Dev: Start frontend and backend",
      "dependsOn": [
        "Backend: FastAPI",
        "Frontend: Vue"
      ],
      "dependsOrder": "parallel",
      "problemMatcher": [],
    },
    {
      "label": "Build: package application",
      "type": "process",
      "command": "python",
      "args": [
        "build.py"
      ],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "presentation": {
        "reveal": "always",
        "panel": "dedicated",
        "group": "build",
        "clear": true
      },
      "problemMatcher": [],
      "group": {
        "kind": "build",
        "isDefault": true
      }
    },
    {
      "label": "Build: package application as single executable",
      "type": "process",
      "command": "python",
      "args": [
        "build.py",
        "--onefile"
      ],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "presentation": {
        "reveal": "always",
        "panel": "dedicated",
        "group": "build",
        "clear": true
      },
      "problemMatcher": [],
      "group": "build"
    }
  ]
}