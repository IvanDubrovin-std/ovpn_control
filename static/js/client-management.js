/**
 * Client Management Module
 * Handles VPN client creation, download, and revocation
 */

/**
 * Show create client modal
 */
function showCreateClientModal() {
    const modal = new bootstrap.Modal(document.getElementById('createClientModal'));
    modal.show();
    
    const clientNameInput = document.getElementById('clientName');
    if (clientNameInput) {
        clientNameInput.focus();
    }
}

/**
 * Create new VPN client
 */
async function createClient() {
    const serverId = document.querySelector('[data-server-id]')?.dataset.serverId;
    const clientName = document.getElementById('clientName').value.trim();
    const clientEmail = document.getElementById('clientEmail').value.trim();
    
    if (!clientName) {
        showAlert('Введите имя клиента');
        return;
    }
    
    // Validate client name format
    if (!isValidClientName(clientName)) {
        showAlert('Имя клиента может содержать только латинские буквы, цифры, дефис и подчеркивание');
        return;
    }
    
    // Validate email if provided
    if (clientEmail && !isValidEmail(clientEmail)) {
        showAlert('Введите корректный email адрес');
        return;
    }
    
    console.log('Creating client:', clientName, 'for server:', serverId);
    
    // Disable button during creation
    const createBtn = document.getElementById('createClientBtn');
    const originalText = showButtonLoading(createBtn, 'Создаем...');
    
    // Prepare request data
    const requestData = {
        client_name: clientName
    };
    
    if (clientEmail) {
        requestData.email = clientEmail;
    }
    
    try {
        const data = await apiRequest(`/api/servers/${serverId}/create-client/`, {
            method: 'POST',
            body: JSON.stringify(requestData)
        });
        
        console.log('API Response data:', data);
        
        if (data.success) {
            showAlert(
                `Клиент "${clientName}" успешно создан!\n\nID: ${data.client_id}\n\nТеперь вы можете скачать конфигурационный файл .ovpn`,
                'Успешно'
            );
            
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('createClientModal'));
            modal.hide();
            
            // Clear form
            document.getElementById('createClientForm').reset();
            
            // Show output in terminal if connected
            if (data.output && isConnected) {
                appendToTerminal('\n=== Client Creation Output ===\n');
                appendToTerminal(data.output + '\n');
                appendToTerminal('=== Client Created Successfully ===\n');
            }
            
            // Reload page to show new client
            reloadPage(1500);
        } else {
            const errorMsg = data.error || data.message || 'Неизвестная ошибка';
            showAlert(`Ошибка создания клиента: ${errorMsg}`, 'Ошибка');
            
            if (data.output && isConnected) {
                appendToTerminal('\n=== Client Creation Error ===\n');
                appendToTerminal(data.output + '\n');
                if (data.error) {
                    appendToTerminal(`Error: ${data.error}\n`);
                }
                appendToTerminal('=== End Error ===\n');
            }
        }
    } catch (error) {
        handleApiError(error, 'Ошибка создания клиента');
    } finally {
        console.log('Client creation request completed');
        restoreButton(createBtn, originalText);
    }
}

/**
 * Download client configuration file
 * @param {string} clientName - Client name
 */
async function downloadClientConfig(clientName) {
    const serverId = document.querySelector('[data-server-id]')?.dataset.serverId;
    
    console.log('Downloading client config:', clientName, 'from server:', serverId);
    
    // Show loading state
    const downloadBtns = document.querySelectorAll(`button[onclick*="downloadClientConfig('${clientName}')"]`);
    downloadBtns.forEach(btn => {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    });
    
    try {
        const response = await fetch(`/api/servers/${serverId}/download-client/${clientName}/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        });
        
        console.log('Download response status:', response.status);
        
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }
        
        // Get filename from Content-Disposition header if available
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `${clientName}.ovpn`;
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
            if (filenameMatch) {
                filename = filenameMatch[1];
            }
        }
        
        const blob = await response.blob();
        console.log('Downloaded file:', filename, 'size:', blob.size);
        
        // Download file
        downloadBlob(blob, filename);
        
        // Show success message
        if (isConnected) {
            appendToTerminal(`\n=== Downloaded: ${filename} ===\n`);
        }
        
        showAlert(`Конфигурационный файл "${filename}" успешно скачан!`, 'Успешно');
    } catch (error) {
        handleApiError(error, 'Ошибка скачивания');
    } finally {
        console.log('Download request completed');
        downloadBtns.forEach(btn => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-download"></i>';
        });
    }
}

/**
 * Revoke client certificate
 * @param {number} clientId - Client ID
 */
async function revokeClient(clientId) {
    if (!confirmAction('Отозвать сертификат клиента? Это действие необратимо.')) {
        return;
    }
    
    console.log('Revoking client:', clientId);
    
    try {
        const data = await apiRequest(`/clients/${clientId}/revoke/`, {
            method: 'POST',
            body: JSON.stringify({})
        });
        
        console.log('Response data:', data);
        
        if (data.success) {
            showAlert('Сертификат успешно отозван: ' + (data.message || ''), 'Успешно');
            reloadPage(1000);
        } else {
            showAlert('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'Ошибка');
        }
    } catch (error) {
        handleApiError(error, 'Ошибка отзыва сертификата');
    }
}
