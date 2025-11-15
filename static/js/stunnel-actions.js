/**
 * STunnel Management Actions
 */

/**
 * Setup STunnel on server
 * @param {number} serverId - Server ID
 */
async function setupStunnel(serverId) {
    if (!confirmAction('Настроить STunnel на этом сервере? Это установит сертификат Let\'s Encrypt.')) {
        return;
    }

    console.log('Setting up STunnel for server:', serverId);
    showStatus('Настраиваем STunnel...', 'info');

    const setupButton = document.getElementById('setup-stunnel-btn');
    const originalHTML = showButtonLoading(setupButton, 'Настраиваем...');

    try {
        const data = await apiRequest(`/api/servers/${serverId}/stunnel/setup/`, {
            method: 'POST'
        });

        console.log('STunnel setup successful:', data);
        showStatus('STunnel успешно настроен!', 'success');

        if (data.output && isConnected) {
            appendToTerminal('\n=== STunnel Setup Output ===\n');
            appendToTerminal(data.output + '\n');
            appendToTerminal('=== Setup Complete ===\n');
        }

        reloadPage(2000);
    } catch (error) {
        console.error('STunnel setup error:', error);
        showStatus(`Ошибка настройки STunnel: ${error.message}`, 'danger');

        if (error.output && isConnected) {
            appendToTerminal('\n=== STunnel Setup Error ===\n');
            appendToTerminal(error.output + '\n');
            appendToTerminal(`Error: ${error.message}\n`);
        }
    } finally {
        restoreButton(setupButton, originalHTML);
    }
}

/**
 * Start STunnel service
 * @param {number} serverId - Server ID
 */
async function startStunnel(serverId) {
    if (!confirmAction('Запустить STunnel сервис?')) {
        return;
    }

    console.log('Starting STunnel for server:', serverId);
    showStatus('Запускаем STunnel...', 'info');

    const startButton = document.getElementById('start-stunnel-btn');
    const originalHTML = showButtonLoading(startButton, 'Запускаем...');

    try {
        const data = await apiRequest(`/api/servers/${serverId}/stunnel/start/`, {
            method: 'POST'
        });

        console.log('STunnel started:', data);
        showStatus('STunnel успешно запущен!', 'success');

        if (data.output && isConnected) {
            appendToTerminal('\n=== STunnel Start Output ===\n');
            appendToTerminal(data.output + '\n');
            appendToTerminal('=== STunnel Started ===\n');
        }

        reloadPage(2000);
    } catch (error) {
        console.error('STunnel start error:', error);
        showStatus(`Ошибка запуска STunnel: ${error.message}`, 'danger');
    } finally {
        restoreButton(startButton, originalHTML);
    }
}

/**
 * Stop STunnel service
 * @param {number} serverId - Server ID
 */
async function stopStunnel(serverId) {
    if (!confirmAction('Остановить STunnel сервис?')) {
        return;
    }

    console.log('Stopping STunnel for server:', serverId);
    showStatus('Останавливаем STunnel...', 'info');

    const stopButton = document.getElementById('stop-stunnel-btn');
    const originalHTML = showButtonLoading(stopButton, 'Останавливаем...');

    try {
        const data = await apiRequest(`/api/servers/${serverId}/stunnel/stop/`, {
            method: 'POST'
        });

        console.log('STunnel stopped:', data);
        showStatus('STunnel успешно остановлен!', 'success');

        if (data.output && isConnected) {
            appendToTerminal('\n=== STunnel Stop Output ===\n');
            appendToTerminal(data.output + '\n');
            appendToTerminal('=== STunnel Stopped ===\n');
        }

        reloadPage(2000);
    } catch (error) {
        console.error('STunnel stop error:', error);
        showStatus(`Ошибка остановки STunnel: ${error.message}`, 'danger');
    } finally {
        restoreButton(stopButton, originalHTML);
    }
}

/**
 * Restart STunnel service
 * @param {number} serverId - Server ID
 */
async function restartStunnel(serverId) {
    if (!confirmAction('Перезапустить STunnel сервис?')) {
        return;
    }

    console.log('Restarting STunnel for server:', serverId);
    showStatus('Перезапускаем STunnel...', 'info');

    const restartButton = document.getElementById('restart-stunnel-btn');
    const originalHTML = showButtonLoading(restartButton, 'Перезапускаем...');

    try {
        const data = await apiRequest(`/api/servers/${serverId}/stunnel/restart/`, {
            method: 'POST'
        });

        console.log('STunnel restarted:', data);
        showStatus('STunnel успешно перезапущен!', 'success');

        if (data.output && isConnected) {
            appendToTerminal('\n=== STunnel Restart Output ===\n');
            appendToTerminal(data.output + '\n');
            appendToTerminal('=== STunnel Restarted ===\n');
        }

        reloadPage(2000);
    } catch (error) {
        console.error('STunnel restart error:', error);
        showStatus(`Ошибка перезапуска STunnel: ${error.message}`, 'danger');
    } finally {
        restoreButton(restartButton, originalHTML);
    }
}
