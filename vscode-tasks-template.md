# VS Code tasks template

This Windows-oriented template provides environment setup, development servers,
verification, and application packaging tasks.

Copy the JSONC block into `${workspaceFolder}\.vscode\tasks.json`, then run
`Dev: initialize environment` once. Use `Dev: Start frontend and backend` for
normal development.

The backend setup installs `pytest` as development tooling in addition to the
pinned runtime requirements. On macOS or Linux, replace the virtual-environment
executable paths with `.venv/bin/python` and remove the `cmd.exe` wrappers
around npm.

```jsonc
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Backend: create venv",
      "type": "process",
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
      "label": "Backend: install development requirements",
      "type": "process",
      "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "pip",
        "install",
        "--upgrade",
        "pip",
        "-r",
        "requirements.txt",
        "pytest"
      ],
      "options": {
        "cwd": "${workspaceFolder}\\backend"
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
      "type": "process",
      "command": "cmd.exe",
      "args": [
        "/d",
        "/c",
        "npm",
        "ci"
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
        "Backend: install development requirements",
        "Frontend: install packages"
      ],
      "dependsOrder": "parallel",
      "problemMatcher": []
    },
    {
      "label": "Backend: FastAPI",
      "type": "process",
      "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "uvicorn",
        "app.main:app",
        "--reload"
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
      "type": "process",
      "command": "cmd.exe",
      "args": [
        "/d",
        "/c",
        "npm",
        "run",
        "dev"
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
      "problemMatcher": []
    },
    {
      "label": "Verify: backend tests",
      "type": "process",
      "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "pytest",
        "-q"
      ],
      "options": {
        "cwd": "${workspaceFolder}\\backend"
      },
      "presentation": {
        "reveal": "always",
        "panel": "dedicated",
        "group": "verify",
        "clear": true
      },
      "problemMatcher": []
    },
    {
      "label": "Verify: frontend type-check",
      "type": "process",
      "command": "cmd.exe",
      "args": [
        "/d",
        "/c",
        "npm",
        "run",
        "type-check"
      ],
      "options": {
        "cwd": "${workspaceFolder}\\frontend"
      },
      "presentation": {
        "reveal": "always",
        "panel": "dedicated",
        "group": "verify",
        "clear": true
      },
      "problemMatcher": []
    },
    {
      "label": "Verify: all",
      "dependsOn": [
        "Verify: backend tests",
        "Verify: frontend type-check"
      ],
      "dependsOrder": "parallel",
      "problemMatcher": []
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
```
