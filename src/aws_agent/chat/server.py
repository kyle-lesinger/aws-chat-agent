"""FastAPI server for AWS Agent chat interface."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
import json
import logging
import asyncio
from pathlib import Path
import uvicorn

from ..core.simple_agent import SimpleAWSAgent
from ..credentials.manager import AWSCredentialManager
from .websocket import WebSocketHandler, ConnectionManager
from .terminal import TerminalManager


logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="AWS Agent Chat", version="0.1.0")

# Add CORS middleware with restricted origins
# In production, replace these with your actual domain
allowed_origins = [
    "http://localhost:8000",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Connection manager for WebSocket connections
connection_manager = ConnectionManager()

# Agent instances per session
agents: Dict[str, SimpleAWSAgent] = {}

# Terminal manager
terminal_manager = TerminalManager(max_sessions=5, session_timeout=30)

# Mount static files directory
static_dir = Path(__file__).parent.parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
async def startup_event():
    """Start terminal manager on startup."""
    await terminal_manager.start()
    logger.info("Terminal manager started")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop terminal manager on shutdown."""
    await terminal_manager.stop()
    logger.info("Terminal manager stopped")


@app.get("/")
async def get_home():
    """Serve the chat interface."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AWS Agent Chat</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
        <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; }
            .header { display: flex; align-items: center; gap: 20px; margin-bottom: 20px; }
            .logo-placeholder { 
                width: 80px; 
                height: 80px; 
                background: white; 
                border-radius: 8px; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                position: relative;
                overflow: hidden;
                padding: 3px;
            }
            .logo-placeholder::after {
                content: '';
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: linear-gradient(45deg, transparent 30%, rgba(255,255,255,0.1) 50%, transparent 70%);
                transform: rotate(45deg);
                transition: all 0.6s;
            }
            .logo-placeholder:hover::after {
                left: 100%;
            }
            .logo-img {
                max-width: 100%;
                max-height: 100%;
                width: auto;
                height: auto;
                transform: scale(1.5);
            }
            .header h1 { margin: 0; flex: 1; }
            .help-section { background: #e3f2fd; border-radius: 8px; padding: 15px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .help-section h3 { margin-top: 0; color: #1976d2; cursor: pointer; user-select: none; }
            .help-section h3:hover { color: #0d47a1; }
            .help-section h3::before { content: '▼ '; font-size: 12px; }
            .help-section.collapsed h3::before { content: '▶ '; }
            .help-section .operations { display: flex; flex-wrap: wrap; gap: 10px; transition: all 0.3s ease; }
            .help-section.collapsed .operations { display: none; }
            .help-section .operation { background: white; padding: 5px 10px; border-radius: 4px; font-size: 14px; cursor: pointer; transition: all 0.2s; }
            .help-section .operation:hover { background: #1976d2; color: white; transform: translateY(-2px); }
            .help-section .category { font-weight: bold; color: #666; margin-right: 5px; }
            .help-section .operation:hover .category { color: #ccc; }
            .chat-box { background: white; border-radius: 8px; padding: 20px; height: 400px; overflow-y: auto; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .message { margin: 10px 0; padding: 10px; border-radius: 5px; white-space: pre-wrap; font-family: monospace; }
            .user-message { background: #007bff; color: white; margin-left: 20%; }
            .agent-message { background: #e9ecef; margin-right: 20%; }
            .input-group { display: flex; gap: 10px; }
            #messageInput { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .status { text-align: center; padding: 10px; color: #666; }
            .profile-section { background: #fff3e0; border-radius: 8px; padding: 15px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .profile-section h3 { margin-top: 0; color: #f57c00; font-size: 18px; font-weight: bold; }
            .profile-selector { display: flex; align-items: center; gap: 10px; }
            .profile-selector label { font-size: 16px; font-weight: bold; color: #e65100; }
            .profile-selector select { 
                padding: 10px 15px; 
                border-radius: 5px; 
                border: 2px solid #ff9800; 
                font-size: 16px; 
                font-weight: bold;
                background: white;
                color: #333;
                cursor: pointer;
                min-width: 200px;
            }
            .profile-selector select:hover { 
                background: #fff3e0; 
                border-color: #f57c00;
            }
            .profile-selector select:focus { 
                outline: none;
                border-color: #e65100;
                box-shadow: 0 0 0 3px rgba(255, 152, 0, 0.2);
            }
            
            /* Tab interface */
            .tabs { display: flex; border-bottom: 2px solid #ddd; margin-bottom: 20px; }
            .tab { padding: 10px 20px; cursor: pointer; background: #f0f0f0; border: 1px solid #ddd; border-bottom: none; margin-right: 5px; border-radius: 5px 5px 0 0; }
            .tab.active { background: white; border-bottom: 1px solid white; margin-bottom: -1px; }
            .tab-content { display: none; }
            .tab-content.active { display: block; }
            
            /* Terminal styles */
            .terminal-container { background: #1e1e1e; border-radius: 8px; padding: 10px; height: 500px; position: relative; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
            .terminal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
            .terminal-title { color: #ccc; font-size: 14px; }
            .terminal-controls { display: flex; gap: 10px; }
            .terminal-btn { padding: 5px 10px; background: #333; color: #ccc; border: none; border-radius: 3px; cursor: pointer; font-size: 12px; }
            .terminal-btn:hover { background: #444; }
            #terminal { height: calc(100% - 40px); }
            .terminal-status { color: #666; font-size: 12px; margin-top: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo-placeholder">
                    <img src="/static/images/nasa-logo.a03a7333.png" alt="NASA Logo" class="logo-img">
                </div>
                <h1>AWS Agent Chat</h1>
            </div>
            <div class="help-section" id="helpSection">
                <h3 onclick="toggleHelp()">Common Operations (click to toggle)</h3>
                <div class="operations">
                    <div class="operation" onclick="useOperation('list buckets')"><span class="category">S3:</span> list buckets</div>
                    <div class="operation" onclick="useOperation('list objects in ')"><span class="category">S3:</span> list objects in [bucket]</div>
                    <div class="operation" onclick="useOperation('download files from s3://[bucket/path] to ~/Downloads')"><span class="category">S3:</span> download files from [bucket/path] to [local]</div>
                    <div class="operation" onclick="useOperation('upload ')"><span class="category">S3:</span> upload [file] to s3://[bucket/key]</div>
                    <div class="operation" onclick="useOperation('upload ~/Documents/report.pdf to s3://my-bucket/reports/2024/')"><span class="category">S3:</span> upload local file to S3</div>
                    <div class="operation" onclick="useOperation('transfer ~/data/ to s3://bucket/backup/ recursive')"><span class="category">S3:</span> upload directory to S3</div>
                    <div class="operation" onclick="useOperation('create directory test/ in bucket my-bucket')"><span class="category">S3:</span> create directory/folder</div>
                    <div class="operation" onclick="useOperation('delete object ')"><span class="category">S3:</span> delete object [key] from [bucket]</div>
                    <div class="operation" onclick="useOperation('create s3 bucket ')"><span class="category">S3:</span> create bucket [name]</div>
                    <div class="operation" onclick="useOperation('show objects in bucket veda-data-store-dev/cattle-heat-story/')"><span class="category">Example:</span> list S3 directory</div>
                    <div class="operation" onclick="useOperation('save objects within bucket veda-data-store-dev/path/ into my ~/tmp directory')"><span class="category">Example:</span> download S3 directory</div>
                </div>
            </div>
            <div class="profile-section">
                <h3>AWS Profile Configuration</h3>
                <div class="profile-selector">
                    <label>Active Profile:</label>
                    <select id="profileSelect">
                        <option value="default">default</option>
                    </select>
                </div>
            </div>
            
            <!-- Tab navigation -->
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chat')">Chat</div>
                <div class="tab" onclick="switchTab('terminal')">Terminal</div>
            </div>
            
            <!-- Chat tab content -->
            <div id="chat-tab" class="tab-content active">
                <div class="chat-box" id="chatBox">
                    <div class="status">Connecting to AWS Agent...</div>
                </div>
                <div class="input-group">
                    <input type="text" id="messageInput" placeholder="Ask me about AWS operations..." disabled>
                    <button id="sendButton" disabled>Send</button>
                </div>
            </div>
            
            <!-- Terminal tab content -->
            <div id="terminal-tab" class="tab-content">
                <div class="terminal-container">
                    <div class="terminal-header">
                        <div class="terminal-title">Terminal</div>
                        <div class="terminal-controls">
                            <button class="terminal-btn" onclick="createTerminal()">New Session</button>
                            <button class="terminal-btn" onclick="clearTerminal()">Clear</button>
                            <button class="terminal-btn" onclick="closeTerminal()">Close</button>
                        </div>
                    </div>
                    <div id="terminal"></div>
                    <div class="terminal-status" id="terminalStatus">Click "New Session" to start</div>
                </div>
            </div>
        </div>
        
        <script>
            let ws = null;
            let sessionId = null;
            let commandHistory = [];
            let historyIndex = -1;
            let currentCommand = '';
            
            // Load command history from localStorage
            function loadCommandHistory() {
                const saved = localStorage.getItem('awsAgentCommandHistory');
                if (saved) {
                    commandHistory = JSON.parse(saved);
                }
            }
            
            // Save command history to localStorage
            function saveCommandHistory() {
                // Keep only last 100 commands
                if (commandHistory.length > 100) {
                    commandHistory = commandHistory.slice(-100);
                }
                localStorage.setItem('awsAgentCommandHistory', JSON.stringify(commandHistory));
            }
            
            // Add command to history
            function addToHistory(command) {
                // Don't add empty commands or duplicates of the last command
                if (command && (commandHistory.length === 0 || commandHistory[commandHistory.length - 1] !== command)) {
                    commandHistory.push(command);
                    saveCommandHistory();
                }
                historyIndex = commandHistory.length;
                currentCommand = '';
            }
            
            function connect() {
                sessionId = Date.now().toString();
                ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);
                
                ws.onopen = function() {
                    document.getElementById('messageInput').disabled = false;
                    document.getElementById('sendButton').disabled = false;
                    document.querySelector('.status').textContent = 'Connected to AWS Agent';
                    loadProfiles();
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'profiles') {
                        updateProfiles(data.profiles);
                    } else if (data.type === 'message') {
                        addMessage(data.content, 'agent');
                    } else if (data.type === 'error') {
                        addMessage('Error: ' + data.content, 'agent');
                    } else if (data.type.startsWith('terminal_')) {
                        handleTerminalMessage(data);
                    }
                };
                
                ws.onclose = function() {
                    document.getElementById('messageInput').disabled = true;
                    document.getElementById('sendButton').disabled = true;
                    document.querySelector('.status').textContent = 'Disconnected. Refreshing...';
                    setTimeout(() => location.reload(), 2000);
                };
            }
            
            function sendMessage() {
                const input = document.getElementById('messageInput');
                const message = input.value.trim();
                if (message && ws && ws.readyState === WebSocket.OPEN) {
                    addToHistory(message);
                    addMessage(message, 'user');
                    ws.send(JSON.stringify({
                        type: 'message',
                        content: message,
                        profile: document.getElementById('profileSelect').value
                    }));
                    input.value = '';
                }
            }
            
            function addMessage(content, sender) {
                const chatBox = document.getElementById('chatBox');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${sender}-message`;
                messageDiv.textContent = content;
                chatBox.appendChild(messageDiv);
                chatBox.scrollTop = chatBox.scrollHeight;
            }
            
            function loadProfiles() {
                ws.send(JSON.stringify({ type: 'get_profiles' }));
            }
            
            function updateProfiles(profiles) {
                const select = document.getElementById('profileSelect');
                select.innerHTML = '';
                profiles.forEach(profile => {
                    const option = document.createElement('option');
                    option.value = profile;
                    option.textContent = profile;
                    select.appendChild(option);
                });
            }
            
            document.getElementById('sendButton').onclick = sendMessage;
            
            // Handle keyboard events for command history
            document.getElementById('messageInput').onkeydown = function(e) {
                const input = e.target;
                
                if (e.key === 'Enter') {
                    e.preventDefault();
                    sendMessage();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    if (commandHistory.length > 0 && historyIndex > 0) {
                        // Save current command if we're at the bottom
                        if (historyIndex === commandHistory.length) {
                            currentCommand = input.value;
                        }
                        historyIndex--;
                        input.value = commandHistory[historyIndex];
                    }
                } else if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    if (historyIndex < commandHistory.length - 1) {
                        historyIndex++;
                        input.value = commandHistory[historyIndex];
                    } else if (historyIndex === commandHistory.length - 1) {
                        historyIndex = commandHistory.length;
                        input.value = currentCommand;
                    }
                }
            };
            
            // Toggle help section
            function toggleHelp() {
                const helpSection = document.getElementById('helpSection');
                helpSection.classList.toggle('collapsed');
            }
            
            // Use operation - put text in input field
            function useOperation(text) {
                const input = document.getElementById('messageInput');
                input.value = text;
                input.focus();
                // Place cursor at the end
                input.setSelectionRange(input.value.length, input.value.length);
            }
            
            // Terminal functionality
            let terminal = null;
            let terminalSessionId = null;
            let fitAddon = null;
            
            // Switch tabs
            function switchTab(tabName) {
                // Update tab buttons
                document.querySelectorAll('.tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                event.target.classList.add('active');
                
                // Update tab content
                document.querySelectorAll('.tab-content').forEach(content => {
                    content.classList.remove('active');
                });
                document.getElementById(tabName + '-tab').classList.add('active');
                
                // Fit terminal if switching to terminal tab
                if (tabName === 'terminal' && terminal && fitAddon) {
                    setTimeout(() => fitAddon.fit(), 100);
                }
            }
            
            // Create terminal
            function createTerminal() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    updateTerminalStatus('WebSocket not connected');
                    return;
                }
                
                if (terminal) {
                    terminal.dispose();
                }
                
                // Create new terminal using the global Terminal from xterm.js
                terminal = new window.Terminal({
                    cursorBlink: true,
                    fontSize: 14,
                    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                    theme: {
                        background: '#1e1e1e',
                        foreground: '#cccccc',
                        cursor: '#ffffff',
                        selection: '#ffffff40'
                    }
                });
                
                // Add fit addon
                fitAddon = new window.FitAddon.FitAddon();
                terminal.loadAddon(fitAddon);
                
                // Open terminal in DOM
                terminal.open(document.getElementById('terminal'));
                fitAddon.fit();
                
                // Handle terminal input
                terminal.onData(data => {
                    if (terminalSessionId && ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({
                            type: 'terminal_input',
                            session_id: terminalSessionId,
                            data: data
                        }));
                    }
                });
                
                // Handle resize
                terminal.onResize(size => {
                    if (terminalSessionId && ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({
                            type: 'terminal_resize',
                            session_id: terminalSessionId,
                            rows: size.rows,
                            cols: size.cols
                        }));
                    }
                });
                
                // Request terminal session
                const size = terminal.rows && terminal.cols ? 
                    { rows: terminal.rows, cols: terminal.cols } : 
                    { rows: 24, cols: 80 };
                    
                ws.send(JSON.stringify({
                    type: 'terminal_create',
                    rows: size.rows,
                    cols: size.cols
                }));
                
                updateTerminalStatus('Creating terminal session...');
            }
            
            // Clear terminal
            function clearTerminal() {
                if (terminal) {
                    terminal.clear();
                }
            }
            
            // Close terminal
            function closeTerminal() {
                if (terminalSessionId && ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        type: 'terminal_close',
                        session_id: terminalSessionId
                    }));
                }
                
                if (terminal) {
                    terminal.dispose();
                    terminal = null;
                    fitAddon = null;
                }
                
                terminalSessionId = null;
                document.getElementById('terminal').innerHTML = '';
                updateTerminalStatus('Terminal closed');
            }
            
            // Update terminal status
            function updateTerminalStatus(message) {
                document.getElementById('terminalStatus').textContent = message;
            }
            
            // Handle terminal messages in WebSocket
            function handleTerminalMessage(data) {
                if (data.type === 'terminal_created') {
                    terminalSessionId = data.session_id;
                    updateTerminalStatus('Terminal connected');
                } else if (data.type === 'terminal_output' && terminal) {
                    terminal.write(data.data);
                } else if (data.type === 'terminal_closed') {
                    closeTerminal();
                }
            }
            
            // Window resize handler
            window.addEventListener('resize', () => {
                if (terminal && fitAddon) {
                    fitAddon.fit();
                }
            });
            
            // Load command history on startup
            loadCommandHistory();
            connect();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for chat communication."""
    await connection_manager.connect(websocket, session_id)
    
    try:
        # Create agent for this session
        credential_manager = AWSCredentialManager()
        agent = SimpleAWSAgent(credential_manager=credential_manager)
        agents[session_id] = agent
        
        # Create WebSocket handler with terminal support
        handler = WebSocketHandler(agent, websocket, terminal_manager, session_id)
        
        # Handle messages
        while True:
            data = await websocket.receive_json()
            await handler.handle_message(data)
            
    except WebSocketDisconnect:
        connection_manager.disconnect(session_id)
        if session_id in agents:
            del agents[session_id]
        logger.info(f"Client {session_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_json({
            "type": "error",
            "content": str(e)
        })


@app.post("/api/chat")
async def chat_endpoint(message: dict):
    """REST API endpoint for chat."""
    try:
        content = message.get("content", "")
        profile = message.get("profile", "default")
        session_id = message.get("session_id", "default")
        
        # Get or create agent for session
        if session_id not in agents:
            credential_manager = AWSCredentialManager()
            agents[session_id] = SimpleAWSAgent(credential_manager=credential_manager)
        
        agent = agents[session_id]
        
        # Get response
        response = await agent.achat(content, profile)
        
        return {
            "response": response,
            "profile": agent.profile,
            "session_id": session_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profiles")
async def get_profiles():
    """Get available AWS profiles."""
    try:
        credential_manager = AWSCredentialManager()
        profiles = credential_manager.list_profiles()
        return {"profiles": profiles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def start_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False, no_browser: bool = False):
    """Start the chat server."""
    import webbrowser
    import threading
    import time
    
    logger.info(f"Starting AWS Agent Chat Server on {host}:{port}")
    
    # Function to open browser after a short delay
    def open_browser():
        time.sleep(1.5)  # Give the server time to start
        url = f"http://localhost:{port}"
        logger.info(f"Opening browser at {url}")
        webbrowser.open(url)
    
    # Start browser opening in a separate thread
    if not reload and not no_browser:  # Don't open browser on reload or if disabled
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
    
    uvicorn.run(
        "aws_agent.chat.server:app",
        host=host,
        port=port,
        reload=reload
    )