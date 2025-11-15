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

/**
 * Update OpenVPN agent on server
 * @param {number} serverId - Server ID
 */
async function updateAgent(serverId) {
    if (!confirmAction('Обновить агент на сервере? Это займет несколько минут.')) {
        return;
    }

    console.log('Starting agent update for server:', serverId);
    showStatus('Обновляем агент на сервере...', 'info');

    // Find all buttons that might need to be disabled
    const updateButtons = document.querySelectorAll('button[onclick*="updateAgent"]');
    const originalHTML = [];
    updateButtons.forEach((btn, index) => {
        originalHTML[index] = showButtonLoading(btn, 'Обновляем...');
    });

    try {
        const data = await apiRequest(`/api/servers/${serverId}/update-agent/`, {
            method: 'POST'
        });

        console.log('Agent update successful:', data);
        showStatus('Агент успешно обновлен!', 'success');

        if (data.output && isConnected) {
            appendToTerminal('\n=== Agent Update Output ===\n');
            appendToTerminal(data.output + '\n');
            appendToTerminal('=== Agent Updated ===\n');
        }

        reloadPage(2000);
    } catch (error) {
        console.error('Agent update error:', error);
        showStatus(`Ошибка обновления агента: ${error.message}`, 'danger');

        if (error.output && isConnected) {
            appendToTerminal('\n=== Agent Update Error ===\n');
            appendToTerminal(error.output + '\n');
            appendToTerminal(`Error: ${error.message}\n`);
        }
    } finally {
        updateButtons.forEach((btn, index) => {
            restoreButton(btn, originalHTML[index]);
        });
    }
}

/**
 * Reinstall OpenVPN server (complete reinstallation)
 * @param {number} serverId - Server ID
 */
async function reinstallOpenVPN(serverId) {
    console.log('reinstallOpenVPN function called with serverId:', serverId);

    // Double confirmation for destructive action
    if (!confirmAction(
        '⚠️ ВНИМАНИЕ! ⚠️\n\n' +
        'Вы собираетесь ПОЛНОСТЬЮ ПЕРЕУСТАНОВИТЬ OpenVPN сервер.\n\n' +
        'Это действие:\n' +
        '• Остановит OpenVPN сервер\n' +
        '• Удалит ВСЕ конфигурации и сертификаты\n' +
        '• Отключит ВСЕХ подключенных клиентов\n' +
        '• Переустановит OpenVPN с нуля\n' +
        '• Пересоздаст все настройки\n\n' +
        'ВСЕ КЛИЕНТСКИЕ СЕРТИФИКАТЫ БУДУТ УДАЛЕНЫ!\n\n' +
        'Продолжить?'
    )) {
        return;
    }

    // Second confirmation
    const confirmText = prompt(
        'Для подтверждения введите название сервера или "REINSTALL":\n\n' +
        '(Это действие необратимо!)'
    );

    if (!confirmText || (confirmText !== 'REINSTALL' && confirmText.toLowerCase() !== 'reinstall')) {
        showStatus('Переустановка отменена', 'warning');
        return;
    }

    console.log('Starting complete OpenVPN reinstallation for server:', serverId);
    showStatus('⚙️ Запускаем полную переустановку OpenVPN...', 'warning');

    // Disable button during reinstallation
    const reinstallButtons = document.querySelectorAll('button[onclick*="reinstallOpenVPN"]');
    const originalHTML = [];
    reinstallButtons.forEach((btn, index) => {
        originalHTML[index] = showButtonLoading(btn, 'Переустанавливаем...');
    });

    try {
        // Show progress messages
        const progressMessages = [
            'Останавливаем OpenVPN сервер...',
            'Удаляем старые конфигурации...',
            'Переустанавливаем OpenVPN...',
            'Настраиваем сервер...',
            'Запускаем OpenVPN...'
        ];

        let currentStep = 0;
        const progressInterval = setInterval(() => {
            if (currentStep < progressMessages.length) {
                showStatus(`⏳ ${progressMessages[currentStep]}`, 'info');
                currentStep++;
            }
        }, 3000);

        const data = await apiRequest(`/api/servers/${serverId}/reinstall-openvpn/`, {
            method: 'POST'
        });

        clearInterval(progressInterval);

        console.log('Reinstallation API Response:', data);

        if (data.success) {
            showStatus('✅ ' + data.message, 'success');

            // Show detailed steps if available
            if (data.steps && isConnected) {
                appendToTerminal('\n=== OpenVPN Reinstallation Steps ===\n');
                data.steps.forEach(step => {
                    appendToTerminal(step + '\n');
                });
                appendToTerminal('=== Reinstallation Complete ===\n');
            }

            // Show service status
            if (data.service_running !== undefined) {
                const statusMsg = data.service_running
                    ? '✅ OpenVPN сервер работает'
                    : '⚠️ OpenVPN установлен, но не запущен (проверьте логи)';
                showStatus(statusMsg, data.service_running ? 'success' : 'warning');
            }

            // Reload page after 3 seconds
            showStatus('Страница будет перезагружена через 3 секунды...', 'info');
            reloadPage(3000);
        } else {
            const errorMsg = data.error || data.message || 'Неизвестная ошибка';
            showStatus(`❌ Ошибка переустановки: ${errorMsg}`, 'danger');

            // Show error steps
            if (data.steps && isConnected) {
                appendToTerminal('\n=== Reinstallation Error ===\n');
                data.steps.forEach(step => {
                    appendToTerminal(step + '\n');
                });
                if (data.error) {
                    appendToTerminal(`\nError: ${data.error}\n`);
                }
                appendToTerminal('=== End Error ===\n');
            }
        }
    } catch (error) {
        console.error('Error reinstalling OpenVPN:', error);
        showStatus(`❌ Ошибка: ${error.message}`, 'danger');

        if (isConnected) {
            appendToTerminal(`\n=== Reinstallation Failed ===\n`);
            appendToTerminal(`Error: ${error.message}\n`);
            appendToTerminal(`Stack: ${error.stack}\n`);
            appendToTerminal('=== End Error ===\n');
        }
    } finally {
        console.log('Reinstallation request completed');
        reinstallButtons.forEach((btn, index) => {
            restoreButton(btn, originalHTML[index]);
        });
    }
}

/**
 * Sync clients with server after reinstallation
 * @param {number} serverId - Server ID
 */
async function syncClients(serverId) {
    console.log('Syncing clients for server:', serverId);
    showStatus('🔄 Синхронизируем клиентов с сервером...', 'info');

    try {
        const data = await apiRequest(`/api/servers/${serverId}/sync-clients/`, {
            method: 'POST'
        });

        console.log('Sync Clients Response:', data);

        if (data.success) {
            const msg = `✅ ${data.message}\n` +
                `Клиентов на сервере: ${data.clients_on_server || 0}\n` +
                `Клиентов в БД: ${data.clients_in_db || 0}\n` +
                `Удалено: ${data.clients_removed || 0}`;

            showStatus(msg, 'success');

            if (data.orphaned_clients && data.orphaned_clients.length > 0) {
                console.log('Removed orphaned clients:', data.orphaned_clients);
            }

            if (data.new_clients && data.new_clients.length > 0) {
                console.log('New clients on server:', data.new_clients);
                showStatus(
                    `⚠️ На сервере найдены новые клиенты, которых нет в БД: ${data.new_clients.join(', ')}`,
                    'warning'
                );
            }

            // Reload page to show updated clients list
            reloadPage(2000);
        } else {
            const errorMsg = data.error || 'Неизвестная ошибка';
            showStatus(`❌ Ошибка синхронизации: ${errorMsg}`, 'danger');
        }
    } catch (error) {
        console.error('Error syncing clients:', error);
        showStatus(`❌ Ошибка: ${error.message}`, 'danger');
    }
}
