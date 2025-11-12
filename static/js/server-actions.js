/**
 * Server Actions Module
 * Handles OpenVPN server installation, configuration, and management
 */

/**
 * Generate and install SSH key on server
 * @param {number} serverId - Server ID
 */
async function generateSSHKey(serverId) {
    // Запрашиваем пароль у пользователя
    const password = prompt('Введите пароль SSH для подключения к серверу:');
    if (!password) {
        showStatus('Отменено: пароль не введен', 'warning');
        return;
    }
    
    // Запрашиваем тип ключа
    const keyType = confirm('Использовать ED25519 ключ?\n\nОК = ED25519 (быстрее, безопаснее, рекомендуется)\nОтмена = RSA 4096 (совместимость со старыми системами)') 
        ? 'ed25519' 
        : 'rsa';
    
    console.log(`Generating ${keyType} SSH key for server:`, serverId);
    showStatus(`Генерируем ${keyType.toUpperCase()} SSH ключ и устанавливаем на сервер...`, 'info');
    
    // Disable button during generation
    const generateButtons = document.querySelectorAll('button[onclick*="generateSSHKey"]');
    const originalHTML = [];
    generateButtons.forEach((btn, index) => {
        originalHTML[index] = showButtonLoading(btn, 'Генерируем...');
    });
    
    try {
        const data = await apiRequest(`/api/servers/${serverId}/generate-ssh-key/`, {
            method: 'POST',
            body: JSON.stringify({
                password: password,
                key_type: keyType,
                clear_password: confirm('Удалить сохраненный пароль после установки ключа?')
            })
        });
        
        console.log('SSH Key Generation Response:', data);
        
        if (data.success) {
            showStatus(data.message, 'success');
            
            // Показываем публичный ключ
            if (data.public_key) {
                const showKey = confirm(
                    `✓ SSH ключ успешно сгенерирован и установлен!\n\n` +
                    `Тип ключа: ${data.key_type.toUpperCase()}\n` +
                    `Приватный ключ: Сохранен в базе данных\n` +
                    `Публичный ключ: Установлен на сервере\n\n` +
                    `Показать публичный ключ?`
                );
                
                if (showKey) {
                    prompt('Публичный ключ (скопируйте при необходимости):', data.public_key);
                }
            }
            
            // Reload page after 1 second to show updated SSH key status
            reloadPage(1000);
        } else {
            const errorMsg = data.error || 'Неизвестная ошибка';
            showStatus(`Ошибка генерации ключа: ${errorMsg}`, 'danger');
        }
    } catch (error) {
        console.error('Error generating SSH key:', error);
        showStatus(`Ошибка: ${error.message}`, 'danger');
    } finally {
        // Restore buttons
        generateButtons.forEach((btn, index) => {
            restoreButton(btn, originalHTML[index]);
        });
    }
}

/**
 * Install OpenVPN on server
 * @param {number} serverId - Server ID
 */
async function installOpenVPN(serverId) {
    if (!confirmAction('Установить OpenVPN на этом сервере?')) {
        return;
    }
    
    console.log('Starting OpenVPN installation for server:', serverId);
    showStatus('Устанавливаем OpenVPN...', 'info');
    
    // Disable button during installation
    const installButtons = document.querySelectorAll('button[onclick*="installOpenVPN"]');
    const originalHTML = [];
    installButtons.forEach((btn, index) => {
        originalHTML[index] = showButtonLoading(btn, 'Устанавливаем...');
    });
    
    try {
        const data = await apiRequest(`/api/servers/${serverId}/install-openvpn/`, {
            method: 'POST'
        });
        
        console.log('API Response data:', data);
        
        if (data.success) {
            showStatus(data.message, 'success');
            
            // Show output in terminal if available
            if (data.output && isConnected) {
                appendToTerminal('\n=== OpenVPN Installation Output ===\n');
                appendToTerminal(data.output + '\n');
                appendToTerminal('=== Installation Complete ===\n');
            }
            
            // Reload page after 2 seconds
            reloadPage(2000);
        } else {
            const errorMsg = data.error || data.message || 'Неизвестная ошибка';
            showStatus(`Ошибка установки: ${errorMsg}`, 'danger');
            
            if (data.output && isConnected) {
                appendToTerminal('\n=== Installation Error ===\n');
                appendToTerminal(data.output + '\n');
                if (data.error) {
                    appendToTerminal(`Error: ${data.error}\n`);
                }
                appendToTerminal('=== End Error ===\n');
            }
        }
    } catch (error) {
        handleApiError(error, 'Ошибка установки');
    } finally {
        console.log('Installation request completed');
        installButtons.forEach((btn, index) => {
            restoreButton(btn, originalHTML[index]);
        });
    }
}

/**
 * Configure OpenVPN server
 * @param {number} serverId - Server ID
 */
async function configureOpenVPN(serverId) {
    if (!confirmAction('Настроить OpenVPN сервер? Это создаст CA, сертификаты и конфигурацию.')) {
        return;
    }
    
    console.log('Starting OpenVPN configuration for server:', serverId);
    showStatus('Настраиваем OpenVPN сервер...', 'info');
    
    const configButtons = document.querySelectorAll('button[onclick*="configureOpenVPN"]');
    const originalHTML = [];
    configButtons.forEach((btn, index) => {
        originalHTML[index] = showButtonLoading(btn, 'Настраиваем...');
    });
    
    try {
        const data = await apiRequest(`/api/servers/${serverId}/configure-openvpn/`, {
            method: 'POST',
            body: JSON.stringify({})
        });
        
        console.log('API Response data:', data);
        
        if (data.success) {
            showStatus(data.message, 'success');
            
            if (data.output && isConnected) {
                appendToTerminal('\n=== OpenVPN Configuration Output ===\n');
                appendToTerminal(data.output + '\n');
                appendToTerminal('=== Configuration Complete ===\n');
            }
        } else {
            const errorMsg = data.error || data.message || 'Неизвестная ошибка';
            showStatus(`Ошибка настройки: ${errorMsg}`, 'danger');
            
            if (data.output && isConnected) {
                appendToTerminal('\n=== Configuration Error ===\n');
                appendToTerminal(data.output + '\n');
                if (data.error) {
                    appendToTerminal(`Error: ${data.error}\n`);
                }
                appendToTerminal('=== End Error ===\n');
            }
        }
    } catch (error) {
        handleApiError(error, 'Ошибка настройки');
    } finally {
        console.log('Configuration request completed');
        configButtons.forEach((btn, index) => {
            restoreButton(btn, originalHTML[index]);
        });
    }
}

/**
 * Start OpenVPN server
 * @param {number} serverId - Server ID
 */
async function startOpenVPN(serverId) {
    if (!confirmAction('Запустить OpenVPN сервер?')) {
        return;
    }
    
    console.log('Starting OpenVPN server for server:', serverId);
    showStatus('Запускаем OpenVPN сервер...', 'info');
    
    const startButtons = document.querySelectorAll('button[onclick*="startOpenVPN"]');
    const originalHTML = [];
    startButtons.forEach((btn, index) => {
        originalHTML[index] = showButtonLoading(btn, 'Запускаем...');
    });
    
    try {
        const data = await apiRequest(`/api/servers/${serverId}/start-openvpn/`, {
            method: 'POST'
        });
        
        console.log('API Response data:', data);
        
        if (data.success) {
            showStatus('OpenVPN сервер успешно запущен!', 'success');
            
            if (data.output && isConnected) {
                appendToTerminal('\n=== OpenVPN Start Output ===\n');
                appendToTerminal(data.output + '\n');
                appendToTerminal('=== Server Started ===\n');
            }
            
            reloadPage(2000);
        } else {
            const errorMsg = data.error || data.message || 'Неизвестная ошибка';
            showStatus(`Ошибка запуска: ${errorMsg}`, 'danger');
            
            if (data.output && isConnected) {
                appendToTerminal('\n=== Start Error ===\n');
                appendToTerminal(data.output + '\n');
                if (data.error) {
                    appendToTerminal(`Error: ${data.error}\n`);
                }
                appendToTerminal('=== End Error ===\n');
            }
        }
    } catch (error) {
        handleApiError(error, 'Ошибка запуска');
    } finally {
        console.log('Start request completed');
        startButtons.forEach((btn, index) => {
            restoreButton(btn, originalHTML[index]);
        });
    }
}

/**
 * Check server status
 * @param {number} serverId - Server ID
 */
async function checkStatus(serverId) {
    console.log('Checking server status:', serverId);
    showStatus('Проверяем статус сервера...', 'info');
    
    try {
        const data = await apiRequest(`/api/servers/${serverId}/check-status/`, {
            method: 'POST'
        });
        
        if (data.success) {
            const statusText = {
                'running': '✅ Работает',
                'stopped': '⛔ Остановлен',
                'error': '❌ Ошибка'
            }[data.status] || data.status;
            
            showStatus(`Статус сервера: ${statusText}`, 
                      data.status === 'running' ? 'success' : 'warning');
            
            // Reload page after 1 second to show updated status
            reloadPage(1000);
        } else {
            showStatus(`Ошибка: ${data.error}`, 'danger');
        }
    } catch (error) {
        console.error('Error checking status:', error);
        showStatus(`Ошибка при проверке статуса: ${error.message}`, 'danger');
    }
}

/**
 * Confirm server deletion
 * @param {number} serverId - Server ID
 */
function confirmDelete(serverId) {
    if (confirmAction('Вы уверены, что хотите удалить этот сервер? Это действие необратимо.')) {
        window.location.href = `/servers/${serverId}/delete/`;
    }
}
