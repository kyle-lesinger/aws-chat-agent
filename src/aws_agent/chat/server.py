"""FastAPI server for AWS Agent chat interface."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
import json
import logging
import asyncio
from pathlib import Path
import uvicorn
import time

from ..core.simple_agent import SimpleAWSAgent
from ..credentials.manager import AWSCredentialManager
from .websocket import WebSocketHandler, ConnectionManager
from .terminal import TerminalManager
from ..credentials.simple_threaded_mfa import SimpleMFACallback


logger = logging.getLogger(__name__)

# Create terminal manager instance
terminal_manager = TerminalManager(max_sessions=5, session_timeout=30)

async def monitor_mfa_notifications():
    """Monitor MFA notification file for updates from terminal."""
    notification_file = Path.home() / ".aws_agent" / "notifications" / "mfa_status.json"
    last_mtime = 0
    
    while True:
        try:
            if notification_file.exists():
                current_mtime = notification_file.stat().st_mtime
                
                if current_mtime > last_mtime:
                    # File has been updated
                    with open(notification_file, 'r') as f:
                        notification = json.load(f)
                    
                    # Check if notification is recent (within last 5 seconds)
                    if time.time() - notification.get('timestamp', 0) < 5:
                        logger.info(f"MFA notification detected: {notification}")
                        
                        # Send to all WebSocket connections
                        if notification['type'] == 'mfa_required':
                            message = {
                                "type": "mfa_terminal_status",
                                "status": "required",
                                "profile": notification.get('profile'),
                                "mfa_device": notification.get('mfa_device')
                            }
                        elif notification['type'] == 'mfa_complete':
                            message = {
                                "type": "mfa_terminal_status",
                                "status": "complete"
                            }
                        else:
                            message = None
                        
                        if message:
                            for session_id, websocket in connection_manager.active_connections.items():
                                try:
                                    await websocket.send_json(message)
                                    logger.info(f"Sent MFA notification to session {session_id}")
                                except Exception as e:
                                    logger.error(f"Failed to send MFA notification to {session_id}: {e}")
                    
                    last_mtime = current_mtime
            
            await asyncio.sleep(0.5)  # Check every 500ms
            
        except Exception as e:
            logger.error(f"Error monitoring MFA notifications: {e}")
            await asyncio.sleep(1)


# Global task reference for MFA monitor
mfa_monitor_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global mfa_monitor_task
    
    # Startup
    await terminal_manager.start()
    logger.info("Terminal manager started")
    
    # Start MFA notification monitor
    mfa_monitor_task = asyncio.create_task(monitor_mfa_notifications())
    logger.info("MFA notification monitor started")
    
    # Initialize server
    logger.info("AWS Agent server initialized")
    
    yield
    
    # Shutdown
    if mfa_monitor_task:
        mfa_monitor_task.cancel()
        try:
            await mfa_monitor_task
        except asyncio.CancelledError:
            pass
    
    await terminal_manager.stop()
    logger.info("Terminal manager stopped")
    

# Create FastAPI app
app = FastAPI(title="AWS Agent Chat", version="0.1.0", lifespan=lifespan)

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

# Mount static files directory
static_dir = Path(__file__).parent.parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Startup and shutdown events are now handled in the lifespan context manager above


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
            
            /* MFA Terminal Relay Box */
            .mfa-input-box {
                background: #f1f8f4;
                border: 3px solid #4caf50;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0 0 10px rgba(76, 175, 80, 0.2);
                width: 250px;
            }
            .mfa-input-box h4 {
                margin: 0 0 10px 0;
                color: #2e7d32;
                font-size: 16px;
            }
            .mfa-status {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 10px;
            }
            .status-indicator {
                font-size: 12px;
                line-height: 1;
            }
            .status-indicator.ready { color: #f44336; } /* Red when ready/idle */
            .status-indicator.waiting { color: #4caf50; animation: pulse 1.5s infinite; } /* Green when MFA needed */
            .status-indicator.error { color: #ff9800; }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            @keyframes flash {
                0%, 100% { background-color: #e8f5e9; }
                50% { background-color: #fff9c4; }
            }
            .mfa-terminal-input {
                width: 100%;
                padding: 8px;
                font-size: 18px;
                text-align: center;
                letter-spacing: 3px;
                border: 2px solid #4caf50;
                border-radius: 4px;
                margin: 10px 0;
                box-sizing: border-box;
            }
            .mfa-terminal-input:focus {
                outline: none;
                border-color: #2e7d32;
            }
            .mfa-terminal-submit {
                width: 100%;
                padding: 8px;
                background: #4caf50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: bold;
            }
            .mfa-terminal-submit:hover {
                background: #45a049;
            }
            .mfa-request-info {
                background: rgba(76, 175, 80, 0.1);
                padding: 5px;
                border-radius: 4px;
                margin-bottom: 5px;
            }
            .mfa-help {
                margin-top: 10px;
                color: #666;
                text-align: center;
            }
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
            
            /* MFA Modal styles */
            .mfa-modal-overlay {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                z-index: 1000;
                align-items: center;
                justify-content: center;
            }
            .mfa-modal-overlay.active {
                display: flex !important;
            }
            .mfa-modal {
                background: white;
                border-radius: 8px;
                padding: 30px;
                max-width: 400px;
                width: 90%;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            }
            .mfa-modal h3 {
                margin-top: 0;
                color: #333;
            }
            .mfa-modal .profile-info {
                background: #f8f9fa;
                padding: 10px;
                border-radius: 4px;
                margin: 15px 0;
                font-family: monospace;
                font-size: 14px;
            }
            .mfa-modal .device-info {
                color: #666;
                font-size: 12px;
                margin-bottom: 20px;
                word-break: break-all;
            }
            .mfa-input-group {
                margin: 20px 0;
            }
            .mfa-input-group label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            .mfa-input-group input {
                width: 100%;
                padding: 10px;
                font-size: 18px;
                border: 2px solid #ddd;
                border-radius: 4px;
                text-align: center;
                letter-spacing: 5px;
                box-sizing: border-box;
            }
            .mfa-input-group input:focus {
                outline: none;
                border-color: #007bff;
            }
            .mfa-buttons {
                display: flex;
                gap: 10px;
                justify-content: flex-end;
                margin-top: 20px;
            }
            .mfa-buttons button {
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
            }
            .mfa-submit {
                background: #007bff;
                color: white;
            }
            .mfa-submit:hover {
                background: #0056b3;
            }
            .mfa-cancel {
                background: #6c757d;
                color: white;
            }
            .mfa-cancel:hover {
                background: #545b62;
            }
            .mfa-error {
                color: #dc3545;
                margin-top: 10px;
                font-size: 14px;
            }
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
                <div style="display: flex; gap: 20px; align-items: flex-start;">
                    <!-- MFA Status Box -->
                    <div class="mfa-input-box">
                        <h4>MFA Terminal Relay</h4>
                        <div id="mfaTerminalStatus" class="mfa-status">
                            <span class="status-indicator ready" id="mfaStatusIndicator">●</span>
                            <span id="mfaStatusText">Ready</span>
                        </div>
                        <div id="mfaTerminalMessage" style="display: none; margin-top: 10px;">
                            <div style="background: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 10px; border-radius: 4px;">
                                <strong>⚠️ Input MFA credentials in terminal</strong>
                                <div style="margin-top: 5px; font-size: 12px;">
                                    Profile: <span id="mfaTerminalProfile"></span>
                                </div>
                            </div>
                        </div>
                        <div class="mfa-help">
                            <small>MFA status indicator</small>
                        </div>
                    </div>
                    
                    <!-- Profile Selector -->
                    <div class="profile-selector" style="flex: 1;">
                        <label>Active Profile:</label>
                        <select id="profileSelect">
                            <option value="default">default</option>
                        </select>
                        <button onclick="loadProfiles()" style="margin-left: 10px; padding: 5px 10px; font-size: 14px;">↻ Refresh</button>
                    </div>
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
        
        <!-- MFA Modal -->
        <div class="mfa-modal-overlay" id="mfaModal">
            <div class="mfa-modal">
                <h3>🔐 MFA Authentication Required</h3>
                <div class="profile-info">
                    Profile: <span id="mfaProfile"></span>
                </div>
                <div class="device-info">
                    MFA Device: <span id="mfaDevice"></span>
                </div>
                <div class="mfa-input-group">
                    <label for="mfaCode">Enter your 6-digit MFA code:</label>
                    <input type="text" 
                           id="mfaCode" 
                           maxlength="6" 
                           pattern="[0-9]{6}" 
                           placeholder="000000"
                           autocomplete="off">
                </div>
                <div class="mfa-error" id="mfaError" style="display: none;"></div>
                <div class="mfa-buttons">
                    <button class="mfa-cancel" onclick="cancelMFA()">Cancel</button>
                    <button class="mfa-submit" onclick="submitMFA()">Submit</button>
                </div>
            </div>
        </div>
        
        <script>
            let ws = null;
            let sessionId = null;
            let commandHistory = [];
            let historyIndex = -1;
            let currentCommand = '';
            let currentMFARequest = null;
 // Keep track of all MFA requests
            
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
                const wsUrl = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsHost = window.location.host;
                const fullWsUrl = `${wsUrl}//${wsHost}/ws/${sessionId}`;
                console.log('Connecting to WebSocket:', fullWsUrl);
                
                ws = new WebSocket(fullWsUrl);
                
                ws.onopen = function() {
                    console.log('WebSocket connected successfully');
                    document.getElementById('messageInput').disabled = false;
                    document.getElementById('sendButton').disabled = false;
                    document.querySelector('.status').textContent = 'Connected to AWS Agent';
                    // Load profiles after connection
                    setTimeout(() => {
                        loadProfiles();
                    }, 500);
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    console.log('📨 WebSocket message received:', data.type, 'at', new Date().toISOString());
                    console.log('Full message data:', data);
                    
                    if (data.type === 'profiles') {
                        updateProfiles(data.profiles);
                    } else if (data.type === 'message') {
                        addMessage(data.content, 'agent');
                    } else if (data.type === 'thinking') {
                        // Show thinking indicator (could add a spinner here)
                        console.log('Agent is thinking...');
                    } else if (data.type === 'error') {
                        addMessage('Error: ' + data.content, 'agent');
                    } else if (data.type === 'mfa_required') {
                        console.log('MFA required message received:', data);
                        showMFAPrompt(data);
                    } else if (data.type === 'mfa_success') {
                        hideMFAPrompt();
                        addMessage(data.message, 'agent');
                    } else if (data.type === 'mfa_terminal_status') {
                        handleMFATerminalStatus(data);
                    } else if (data.type.startsWith('terminal_')) {
                        handleTerminalMessage(data);
                    }
                };
                
                ws.onerror = function(error) {
                    console.error('WebSocket error:', error);
                    document.querySelector('.status').textContent = 'Connection error';
                };
                
                ws.onclose = function(event) {
                    console.log('WebSocket closed:', event.code, event.reason);
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
                console.log('Loading profiles...');
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    console.error('WebSocket not connected');
                    return;
                }
                ws.send(JSON.stringify({ type: 'get_profiles' }));
            }
            
            function updateProfiles(profiles) {
                console.log('Updating profiles:', profiles);
                const select = document.getElementById('profileSelect');
                if (!select) {
                    console.error('Profile select element not found!');
                    return;
                }
                select.innerHTML = '';
                if (!profiles || profiles.length === 0) {
                    console.warn('No profiles received');
                    const option = document.createElement('option');
                    option.value = 'default';
                    option.textContent = 'default';
                    select.appendChild(option);
                    return;
                }
                profiles.forEach(profile => {
                    const option = document.createElement('option');
                    option.value = profile;
                    option.textContent = profile;
                    select.appendChild(option);
                });
                console.log('Profile select updated with', profiles.length, 'profiles');
            }
            
            // Handle profile selection
            document.getElementById('profileSelect').onchange = function(e) {
                const profile = e.target.value;
                console.log('Profile selected:', profile);
                
                // Just log for now, no need to send to server
            };
            
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
                console.log('Creating terminal...');
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    updateTerminalStatus('WebSocket not connected');
                    return;
                }
                
                if (terminal) {
                    terminal.dispose();
                }
                
                try {
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
                } catch (error) {
                    console.error('Failed to create terminal:', error);
                    updateTerminalStatus('Error: ' + error.message);
                }
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
            
            // MFA Modal Functions
            function showMFAPrompt(data) {
                try {
                    console.log('showMFAPrompt called with:', data);
                    currentMFARequest = data;
                    document.getElementById('mfaProfile').textContent = data.profile;
                    document.getElementById('mfaDevice').textContent = data.mfa_device;
                    document.getElementById('mfaCode').value = '';
                    document.getElementById('mfaError').style.display = 'none';
                    
                    // Force modal to display
                    const modal = document.getElementById('mfaModal');
                    modal.style.display = 'flex';
                    modal.classList.add('active');
                    
                    console.log('MFA modal should now be visible');
                    console.log('Modal display:', window.getComputedStyle(modal).display);
                    
                    // Focus on input
                    setTimeout(() => {
                        document.getElementById('mfaCode').focus();
                    }, 100);
                } catch (error) {
                    console.error('Error showing MFA prompt:', error);
                }
            }
            
            function hideMFAPrompt() {
                document.getElementById('mfaModal').classList.remove('active');
                currentMFARequest = null;
            }
            
            function submitMFA() {
                const mfaCode = document.getElementById('mfaCode').value;
                
                if (!mfaCode || mfaCode.length !== 6) {
                    showMFAError('Please enter a 6-digit code');
                    return;
                }
                
                if (!currentMFARequest) {
                    showMFAError('Invalid MFA request');
                    return;
                }
                
                // Send MFA response
                ws.send(JSON.stringify({
                    type: 'mfa_response',
                    profile: currentMFARequest.profile,
                    mfa_code: mfaCode,
                    request_id: currentMFARequest.request_id
                }));
                
                // Show loading state
                document.getElementById('mfaCode').disabled = true;
                document.querySelector('.mfa-submit').disabled = true;
                document.querySelector('.mfa-submit').textContent = 'Verifying...';
            }
            
            function cancelMFA() {
                hideMFAPrompt();
                addMessage('MFA authentication cancelled', 'agent');
            }
            
            function showMFAError(error) {
                const errorDiv = document.getElementById('mfaError');
                errorDiv.textContent = error;
                errorDiv.style.display = 'block';
                // Reset button state
                document.getElementById('mfaCode').disabled = false;
                document.querySelector('.mfa-submit').disabled = false;
                document.querySelector('.mfa-submit').textContent = 'Submit';
            }
            
            // Handle Enter key in MFA input
            document.getElementById('mfaCode').addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    submitMFA();
                }
            });
            
            // Only allow numbers in MFA input
            document.getElementById('mfaCode').addEventListener('input', function(e) {
                e.target.value = e.target.value.replace(/[^0-9]/g, '');
            });
            
            // Terminal MFA Active notification (when terminal is prompting)
            function handleTerminalMFAActive(data) {
                console.log('Terminal MFA is active:', data);
                
                // Update UI to show terminal is waiting for MFA
                document.getElementById('mfaStatusIndicator').className = 'status-indicator waiting';
                document.getElementById('mfaStatusText').textContent = 'Enter MFA in Terminal';
                document.getElementById('mfaTerminalProfile').textContent = data.profile;
                
                // Show message in the box
                const helpDiv = document.querySelector('.mfa-help small');
                if (helpDiv) {
                    helpDiv.textContent = '⚠️ Check your terminal window for MFA prompt';
                    helpDiv.style.color = '#ff9800';
                }
                
                // Flash the box
                const box = document.querySelector('.mfa-input-box');
                box.style.animation = 'flash 0.5s';
                setTimeout(() => box.style.animation = '', 500);
                
                // Add message to chat
                addMessage(`🔐 MFA required for ${data.profile} - Please check your terminal window`, 'agent');
            }
            
            function handleTerminalMFAComplete(data) {
                console.log('Terminal MFA completed:', data);
                
                // Reset UI
                document.getElementById('mfaStatusIndicator').className = 'status-indicator ready';
                document.getElementById('mfaStatusText').textContent = 'Ready';
                
            }
            
            // Handle MFA terminal status updates
            function handleMFATerminalStatus(data) {
                console.log('MFA Terminal Status:', data);
                
                const indicator = document.getElementById('mfaStatusIndicator');
                const statusText = document.getElementById('mfaStatusText');
                const messageDiv = document.getElementById('mfaTerminalMessage');
                const profileSpan = document.getElementById('mfaTerminalProfile');
                
                if (data.status === 'required') {
                    // Show MFA required status (green)
                    indicator.className = 'status-indicator waiting';
                    statusText.textContent = 'MFA Required';
                    profileSpan.textContent = data.profile;
                    messageDiv.style.display = 'block';
                    
                    // Flash the box to get attention
                    const box = document.querySelector('.mfa-input-box');
                    if (box) {
                        box.style.animation = 'flash 0.5s';
                        setTimeout(() => box.style.animation = '', 500);
                    }
                    
                    // Auto-reset after 60 seconds (MFA timeout)
                    setTimeout(() => {
                        if (indicator.className === 'status-indicator waiting') {
                            indicator.className = 'status-indicator ready';
                            statusText.textContent = 'Ready';
                            messageDiv.style.display = 'none';
                        }
                    }, 60000);
                } else if (data.status === 'complete') {
                    // MFA completed - back to ready (red)
                    indicator.className = 'status-indicator ready';
                    statusText.textContent = 'Ready';
                    messageDiv.style.display = 'none';
                }
            }
            
            // Load command history on startup
            loadCommandHistory();
            connect();
            
            // Debug functions for profiles
            window.ProfileDebug = {
                loadProfiles: loadProfiles,
                checkWebSocket: function() {
                    console.log('WebSocket state:', ws ? ws.readyState : 'null');
                    console.log('WebSocket OPEN:', ws && ws.readyState === WebSocket.OPEN);
                },
                testGetProfiles: function() {
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        console.log('Sending get_profiles request...');
                        ws.send(JSON.stringify({ type: 'get_profiles' }));
                    } else {
                        console.error('WebSocket not connected');
                    }
                }
            };
            
            // Debug functions for MFA modal
            window.MFADebug = {
                test: function() {
                    console.log('Testing MFA modal...');
                    showMFAPrompt({
                        profile: 'ghgc-smce',
                        mfa_device: 'arn:aws:iam::597746869805:mfa/iphone',
                        request_id: 'test-' + Date.now()
                    });
                },
                debug: function() {
                    const modal = document.getElementById('mfaModal');
                    console.log('MFA Modal Debug:');
                    console.log('- Exists:', !!modal);
                    console.log('- Display:', modal?.style.display);
                    console.log('- Classes:', modal?.className);
                    console.log('- Computed display:', window.getComputedStyle(modal).display);
                },
                forceShow: function() {
                    const modal = document.getElementById('mfaModal');
                    if (modal) {
                        modal.style.cssText = 'display: flex !important; position: fixed !important; top: 0 !important; left: 0 !important; width: 100% !important; height: 100% !important; background: rgba(0,0,0,0.5) !important; z-index: 9999 !important; align-items: center !important; justify-content: center !important;';
                    }
                }
            };
            console.log('Debug tools loaded:');
            console.log('- ProfileDebug.loadProfiles() - Manually load profiles');
            console.log('- ProfileDebug.checkWebSocket() - Check WebSocket connection');
            console.log('- ProfileDebug.testGetProfiles() - Test profile loading');
            console.log('- MFADebug.test() - Test MFA modal');
            console.log('- MFADebug.debug() - Check MFA modal state');
            console.log('- MFADebug.forceShow() - Force show MFA modal');
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for chat communication."""
    await connection_manager.connect(websocket, session_id)
    
    credential_manager = None
    agent = None
    handler = None
    
    try:
        # Create credential manager first
        credential_manager = AWSCredentialManager()
        
        # Use simple MFA callback and set the connection manager
        SimpleMFACallback.set_connection_manager(connection_manager)
        mfa_callback = SimpleMFACallback()
        credential_manager.set_mfa_callback(mfa_callback)
        
        # Try to create agent, but handle failure gracefully
        try:
            agent = SimpleAWSAgent(credential_manager=credential_manager)
            agents[session_id] = agent
            
            # Create WebSocket handler with terminal support
            handler = WebSocketHandler(agent, websocket, terminal_manager, session_id)
            
        except Exception as e:
            logger.warning(f"Failed to create full agent: {e}")
            
            # Check if it's an OpenAI API key issue
            if "api_key" in str(e).lower() or "openai" in str(e).lower():
                logger.info("Creating mock agent (OpenAI not configured)")
                
                # Use mock agent
                from ..core.mock_agent import MockAWSAgent
                agent = MockAWSAgent(credential_manager=credential_manager)
                agents[session_id] = agent
                
                # Create handler with mock agent
                handler = WebSocketHandler(agent, websocket, terminal_manager, session_id)
                
                # Send info to client
                await websocket.send_json({
                    "type": "info",
                    "content": "Running in mock mode (no OpenAI API key). Profile operations are fully functional."
                })
            else:
                logger.info("Creating profile-only handler for basic operations")
                
                # Use lightweight profile handler
                from .profile_only_handler import ProfileOnlyHandler
                handler = ProfileOnlyHandler(websocket, credential_manager)
                
                # Send warning to client
                await websocket.send_json({
                    "type": "warning",
                    "content": f"Limited functionality: {str(e)}. Profile operations are available."
                })
        
        # Handle messages
        while True:
            data = await websocket.receive_json()
            
            # Route to appropriate handler
            if hasattr(handler, 'handle_message'):
                await handler.handle_message(data)
            else:
                # Profile-only handler
                message_type = data.get("type")
                if message_type == "get_profiles":
                    await handler.handle_get_profiles()
                else:
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Agent not initialized. Only profile operations available."
                    })
            
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