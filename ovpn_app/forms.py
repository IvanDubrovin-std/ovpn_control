"""
Django forms for OpenVPN management system
"""

from django import forms
from django.core.validators import validate_ipv4_address
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML
from crispy_forms.bootstrap import FormActions

from .models import OpenVPNServer, ClientCertificate, CertificateAuthority


class ServerForm(forms.ModelForm):
    """Form for creating/editing OpenVPN servers"""
    
    dns1 = forms.GenericIPAddressField(
        protocol='IPv4',
        label='DNS сервер 1',
        initial='8.8.8.8',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '8.8.8.8'})
    )
    dns2 = forms.GenericIPAddressField(
        protocol='IPv4',
        label='DNS сервер 2',
        initial='8.8.4.4',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '8.8.4.4'})
    )
    
    class Meta:
        model = OpenVPNServer
        fields = [
            'name', 'description', 'host', 'ssh_port', 'ssh_username',
            'ssh_password', 'ssh_key_path', 'ssh_private_key', 'openvpn_port', 'openvpn_protocol',
            'server_subnet', 'server_netmask'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'host': forms.TextInput(attrs={'class': 'form-control'}),
            'ssh_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'ssh_username': forms.TextInput(attrs={'class': 'form-control'}),
            'ssh_password': forms.PasswordInput(attrs={'class': 'form-control'}),
            'ssh_key_path': forms.TextInput(attrs={'class': 'form-control'}),
            'ssh_private_key': forms.Textarea(attrs={'rows': 6, 'class': 'form-control', 'placeholder': 'Вставьте SSH приватный ключ...'}),
            'openvpn_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'openvpn_protocol': forms.Select(attrs={'class': 'form-select'}),
            'server_subnet': forms.TextInput(attrs={'class': 'form-control'}),
            'server_netmask': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load DNS servers from instance if editing
        if self.instance and self.instance.pk and self.instance.dns_servers:
            dns_servers = self.instance.get_dns_servers_list()
            if len(dns_servers) >= 1:
                self.initial['dns1'] = dns_servers[0]
            if len(dns_servers) >= 2:
                self.initial['dns2'] = dns_servers[1]
        # Set default DNS servers if new server
        elif not self.instance.pk:
            self.initial['dns1'] = '8.8.8.8'
            self.initial['dns2'] = '8.8.4.4'
    
    def clean_host(self):
        host = self.cleaned_data.get('host')
        if host:
            try:
                validate_ipv4_address(host)
            except ValidationError:
                raise forms.ValidationError('Введите корректный IPv4 адрес.')
        return host
    
    def clean_ssh_port(self):
        port = self.cleaned_data.get('ssh_port')
        if port and (port < 1 or port > 65535):
            raise forms.ValidationError('SSH порт должен быть от 1 до 65535.')
        return port
    
    def clean_openvpn_port(self):
        port = self.cleaned_data.get('openvpn_port')
        if port and (port < 1 or port > 65535):
            raise forms.ValidationError('OpenVPN порт должен быть от 1 до 65535.')
        return port
    
    def clean(self):
        cleaned_data = super().clean()
        ssh_password = cleaned_data.get('ssh_password')
        ssh_key_path = cleaned_data.get('ssh_key_path')
        
        if not ssh_password and not ssh_key_path:
            raise forms.ValidationError(
                'Необходимо указать либо SSH пароль, либо путь к SSH ключу.'
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Update DNS servers
        dns1 = self.cleaned_data.get('dns1')
        dns2 = self.cleaned_data.get('dns2')
        dns_servers = []
        
        if dns1:
            dns_servers.append(dns1)
        if dns2:
            dns_servers.append(dns2)
        
        # Set default if no DNS provided
        if not dns_servers:
            dns_servers = ['8.8.8.8', '8.8.4.4']
        
        instance.dns_servers = dns_servers
        
        if commit:
            instance.save()
        
        return instance


class ClientCertificateForm(forms.ModelForm):
    """Form for creating client certificates"""
    
    class Meta:
        model = ClientCertificate
        fields = ['server', 'name', 'email', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Crispy forms helper
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'server',
            Row(
                Column('name', css_class='form-group col-md-6 mb-0'),
                Column('email', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'description',
            FormActions(
                Submit('submit', 'Создать сертификат', css_class='btn-primary'),
                HTML('<a href="{% url "client_list" %}" class="btn btn-secondary ml-2">Отмена</a>')
            )
        )
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        server = self.cleaned_data.get('server')
        
        if name and server:
            # Check if client with this name already exists on this server
            if ClientCertificate.objects.filter(
                server=server, 
                name=name
            ).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise forms.ValidationError(
                    f'Клиент с именем "{name}" уже существует на этом сервере.'
                )
        
        return name


class ServerConfigForm(forms.ModelForm):
    """Form for updating server configuration"""
    
    dns1 = forms.GenericIPAddressField(
        protocol='IPv4',
        label='DNS сервер 1',
        initial='8.8.8.8'
    )
    dns2 = forms.GenericIPAddressField(
        protocol='IPv4',
        label='DNS сервер 2',
        initial='8.8.4.4'
    )
    
    class Meta:
        model = OpenVPNServer
        fields = [
            'openvpn_port', 'openvpn_protocol', 'server_subnet', 
            'server_netmask'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load current DNS servers
        if self.instance and self.instance.dns_servers:
            dns_servers = self.instance.get_dns_servers_list()
            if len(dns_servers) >= 1:
                self.initial['dns1'] = dns_servers[0]
            if len(dns_servers) >= 2:
                self.initial['dns2'] = dns_servers[1]
        
        # Crispy forms helper
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h4>OpenVPN Configuration</h4>'),
            Row(
                Column('openvpn_port', css_class='form-group col-md-6 mb-0'),
                Column('openvpn_protocol', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('server_subnet', css_class='form-group col-md-6 mb-0'),
                Column('server_netmask', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            HTML('<h4>DNS Servers</h4>'),
            Row(
                Column('dns1', css_class='form-group col-md-6 mb-0'),
                Column('dns2', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            FormActions(
                Submit('submit', 'Обновить конфигурацию', css_class='btn-primary'),
            )
        )
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Update DNS servers
        dns1 = self.cleaned_data.get('dns1')
        dns2 = self.cleaned_data.get('dns2')
        dns_servers = []
        
        if dns1:
            dns_servers.append(dns1)
        if dns2:
            dns_servers.append(dns2)
        
        instance.dns_servers = dns_servers
        
        if commit:
            instance.save()
        
        return instance


class ServerSearchForm(forms.Form):
    """Form for searching servers"""
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Поиск по имени, IP или описанию...',
            'class': 'form-control'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'Все статусы')] + OpenVPNServer.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ClientSearchForm(forms.Form):
    """Form for searching clients"""
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Поиск по имени или email...',
            'class': 'form-control'
        })
    )
    server = forms.ModelChoiceField(
        queryset=OpenVPNServer.objects.all(),
        required=False,
        empty_label='Все серверы',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    status = forms.ChoiceField(
        choices=[('', 'Все статусы')] + ClientCertificate.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ConnectionFilterForm(forms.Form):
    """Form for filtering connections"""
    
    server = forms.ModelChoiceField(
        queryset=OpenVPNServer.objects.filter(status='running'),
        required=False,
        empty_label='Все серверы',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('server', css_class='form-group col-md-4 mb-0'),
                Column(
                    Submit('filter', 'Фильтровать', css_class='btn-primary mt-4'),
                    css_class='form-group col-md-2 mb-0'
                ),
                css_class='form-row'
            )
        )
