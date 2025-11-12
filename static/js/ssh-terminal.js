/**
 * SSH Terminal Module
 * Handles SSH connection and terminal interactions
 */

let sshSocket = null;
let isConnected = false;

/**
 * Connect to SSH
 */
function connectSSH() {
    if (isConnected) return;
    
    isConnected = true;
    showStatus('Подключение к SSH...', 'info');
    document.getElementById('connect-btn').disabled = true;
    document.getElementById('disconnect-btn').disabled = false;
    document.getElementById('terminal-input').disabled = false;
    document.getElementById('terminal-container').style.display = 'block';
    document.getElementById('terminal-placeholder').style.display = 'none';
    
    // Get server details from page
    const serverHost = document.querySelector('[data-server-host]')?.dataset.serverHost || 'server';
    const serverUsername = document.querySelector('[data-server-username]')?.dataset.serverUsername || 'user';
    const serverPort = document.querySelector('[data-server-port]')?.dataset.serverPort || '22';
    
    // Simulate SSH connection
    setTimeout(() => {
        appendToTerminal(`Connecting to ${serverUsername}@${serverHost}:${serverPort}...\n`);
        appendToTerminal('SSH Terminal (Demo Mode)\n');
        appendToTerminal(`Welcome to ${serverHost}\n`);
        appendToTerminal(`${serverUsername}@${serverHost}:~$ `);
        showStatus('SSH подключение установлено (Demo Mode)', 'success');
        setTimeout(() => hideStatus(), 3000);
    }, 1000);
}

/**
 * Disconnect from SSH
 */
function disconnectSSH() {
    isConnected = false;
    document.getElementById('connect-btn').disabled = false;
    document.getElementById('disconnect-btn').disabled = true;
    document.getElementById('terminal-input').disabled = true;
    showStatus('Отключено от SSH', 'info');
}

/**
 * Send command to server
 * @param {string} command - Command to execute
 */
function sendCommand(command) {
    if (!isConnected) return;
    
    if (!command.trim()) return;
    
    // Add command to terminal
    appendToTerminal(command + '\n');
    
    // Get server ID from page
    const serverId = document.querySelector('[data-server-id]')?.dataset.serverId;
    
    if (!serverId) {
        appendToTerminal('Error: Server ID not found\n');
        return;
    }
    
    // Send via AJAX to API endpoint
    apiRequest(`/api/servers/${serverId}/ssh-command/`, {
        method: 'POST',
        body: JSON.stringify({ command: command })
    })
    .then(data => {
        if (data.output) {
            appendToTerminal(data.output);
        }
        const serverUsername = document.querySelector('[data-server-username]')?.dataset.serverUsername || 'user';
        const serverHost = document.querySelector('[data-server-host]')?.dataset.serverHost || 'server';
        appendToTerminal(`${serverUsername}@${serverHost}:~$ `);
    })
    .catch(error => {
        appendToTerminal('Error: ' + error.message + '\n');
        const serverUsername = document.querySelector('[data-server-username]')?.dataset.serverUsername || 'user';
        const serverHost = document.querySelector('[data-server-host]')?.dataset.serverHost || 'server';
        appendToTerminal(`${serverUsername}@${serverHost}:~$ `);
    });
}

/**
 * Append text to terminal output
 * @param {string} text - Text to append
 */
function appendToTerminal(text) {
    const output = document.getElementById('terminal-output');
    if (!output) return;
    
    const newContent = document.createElement('div');
    newContent.innerHTML = escapeHtml(text).replace(/\n/g, '<br>').replace(/ /g, '&nbsp;');
    output.appendChild(newContent);
    
    // Auto-scroll to bottom
    const container = document.getElementById('terminal-container');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

/**
 * Clear terminal output
 */
function clearTerminal() {
    const output = document.getElementById('terminal-output');
    if (output) {
        output.innerHTML = '';
    }
}

/**
 * Initialize terminal event listeners
 */
function initTerminal() {
    const terminalInput = document.getElementById('terminal-input');
    if (!terminalInput) return;
    
    terminalInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            const command = this.value.trim();
            if (command) {
                sendCommand(command);
                this.value = '';
            }
        }
    });
    
    // Focus terminal input when clicking on terminal
    const terminalContainer = document.getElementById('terminal-container');
    if (terminalContainer) {
        terminalContainer.addEventListener('click', function() {
            if (!terminalInput.disabled) {
                terminalInput.focus();
            }
        });
    }
}

// Initialize terminal when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTerminal);
} else {
    initTerminal();
}
