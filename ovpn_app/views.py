"""
Django views for OpenVPN management system
"""


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import ClientCertificateForm, ServerForm
from .models import ClientCertificate, OpenVPNServer, ServerTask, VPNConnection
from .services.server_service import ServerManagementService
from .services.client_service import ClientManagementService
from .ssh_service import SSHService


class DashboardView(LoginRequiredMixin, ListView):
    """Main dashboard view"""

    template_name = "ovpn_app/dashboard.html"
    context_object_name = "servers"
    model = OpenVPNServer

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistics
        context.update(
            {
                "total_servers": OpenVPNServer.objects.count(),
                "running_servers": OpenVPNServer.objects.filter(status="running").count(),
                "total_clients": ClientCertificate.objects.count(),
                "active_connections": VPNConnection.objects.count(),
                "recent_tasks": ServerTask.objects.select_related("server")[:5],
            }
        )

        return context


class ServerListView(LoginRequiredMixin, ListView):
    """Server list view"""

    model = OpenVPNServer
    template_name = "ovpn_app/server_list.html"
    context_object_name = "servers"
    paginate_by = 10

    def get_queryset(self):
        queryset = OpenVPNServer.objects.all()
        search_query = self.request.GET.get("search")

        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(host__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        return queryset.order_by("-created_at")


class ServerDetailView(LoginRequiredMixin, DetailView):
    """Server detail view"""

    model = OpenVPNServer
    template_name = "ovpn_app/server_detail.html"
    context_object_name = "server"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        server = self.get_object()

        context.update(
            {
                "clients": server.clients.all()[:10],
                "active_clients_count": server.clients.filter(revoked_at__isnull=True).count(),
                "recent_tasks": server.tasks.all()[:5],
                "active_connections": VPNConnection.objects.filter(client__server=server).count(),
            }
        )

        return context


class ServerCreateView(LoginRequiredMixin, CreateView):
    """Create new server"""

    model = OpenVPNServer
    form_class = ServerForm
    template_name = "ovpn_app/server_form.html"
    success_url = reverse_lazy("ovpn_app:server_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Сервер "{form.instance.name}" успешно создан.')
        return super().form_valid(form)


class ServerUpdateView(LoginRequiredMixin, UpdateView):
    """Update server"""

    model = OpenVPNServer
    form_class = ServerForm
    template_name = "ovpn_app/server_form.html"

    def get_success_url(self):
        return reverse_lazy("ovpn_app:server_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, f'Сервер "{form.instance.name}" успешно обновлен.')
        return super().form_valid(form)


class ServerDeleteView(LoginRequiredMixin, DeleteView):
    """Delete server"""

    model = OpenVPNServer
    template_name = "ovpn_app/server_delete.html"
    success_url = reverse_lazy("ovpn_app:server_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, f'Сервер "{self.object.name}" успешно удален.')
        return super().delete(request, *args, **kwargs)


@login_required
@require_http_methods(["POST"])
def install_openvpn(request, server_id):
    """Install OpenVPN on server"""
    server = get_object_or_404(OpenVPNServer, id=server_id)

    if server.status in ["installing", "running"]:
        messages.warning(request, "OpenVPN уже установлен или устанавливается.")
        return redirect("server_detail", pk=server_id)

    try:
        # TODO: Migrate to new architecture - views should call API endpoints, not services directly
        # Start installation task
        # openvpn_service = OpenVPNService()
        # task = openvpn_service.install_server(server, request.user)

        messages.warning(request, "Функция временно недоступна. Используйте API endpoint: POST /api/servers/{id}/reinstall/")
        return redirect("server_detail", pk=server_id)

        # messages.info(request, f"Установка OpenVPN запущена. Задача: {task.task_id}")
        # return redirect("server_detail", pk=server_id)

    except Exception as e:
        messages.error(request, f"Ошибка при запуске установки: {str(e)}")
        return redirect("server_detail", pk=server_id)


@login_required
@require_http_methods(["POST"])
def check_server_status(request, server_id):
    """Check server status"""
    server = get_object_or_404(OpenVPNServer, id=server_id)

    try:
        ssh_service = SSHService()
        status = ssh_service.check_openvpn_status(server)

        server.status = status
        server.last_check = timezone.now()
        server.save()

        return JsonResponse(
            {"success": True, "status": status, "last_check": server.last_check.isoformat()}
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


class ClientListView(LoginRequiredMixin, ListView):
    """Client certificates list"""

    model = ClientCertificate
    template_name = "ovpn_app/clients/list.html"
    context_object_name = "clients"
    paginate_by = 20

    def get_queryset(self):
        queryset = ClientCertificate.objects.select_related("server").all()

        # Filter by server
        server_id = self.request.GET.get("server")
        if server_id:
            queryset = queryset.filter(server_id=server_id)

        # Search
        search_query = self.request.GET.get("search")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["servers"] = OpenVPNServer.objects.filter(status="running")
        context["selected_server"] = self.request.GET.get("server")
        return context


class ClientCreateView(LoginRequiredMixin, CreateView):
    """Create client certificate"""

    model = ClientCertificate
    form_class = ClientCertificateForm
    template_name = "ovpn_app/clients/create.html"
    success_url = reverse_lazy("ovpn_app:client_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filter servers to only show running ones
        form.fields["server"].queryset = OpenVPNServer.objects.filter(status="running")
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user

        try:
            # TODO: Migrate to new architecture - use ClientManagementService with async
            # Create certificate using OpenVPN service
            # openvpn_service = OpenVPNService()
            # openvpn_service.create_client_certificate(
            #     form.instance.server, form.instance.name, form.instance.email or ""
            # )

            messages.warning(
                self.request, "Функция временно недоступна. Используйте API endpoint: POST /api/servers/{id}/clients/"
            )
            return self.form_invalid(form)

            # messages.success(
            #     self.request, f'Сертификат для клиента "{form.instance.name}" успешно создан.'
            # )
            # return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f"Ошибка при создании сертификата: {str(e)}")
            return self.form_invalid(form)


@login_required
@require_http_methods(["POST"])
@login_required
@require_POST
def revoke_client(request, client_id):
    """Revoke client certificate"""
    client = get_object_or_404(ClientCertificate, id=client_id)

    if client.status == "revoked":
        return JsonResponse({"success": False, "error": "Сертификат уже отозван."}, status=400)

    try:
        # Simple revoke without OpenVPN service (just update status)
        client.revoke()

        return JsonResponse(
            {"success": True, "message": f'Сертификат клиента "{client.name}" успешно отозван.'}
        )

    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Ошибка при отзыве сертификата: {str(e)}"}, status=500
        )


@login_required
def download_client_config(request, client_id):
    """Download client OpenVPN configuration"""
    import asyncio
    import logging

    logger = logging.getLogger(__name__)

    client = get_object_or_404(ClientCertificate, id=client_id)
    server = client.server

    logger.info(f"Downloading config for client {client.name} from server {server.name}")

    if not client.is_valid():
        logger.warning(f"Client {client.name} certificate is invalid")
        messages.error(request, "Сертификат недействителен.")
        return redirect("ovpn_app:client_list")

    try:
        # Use new ClientManagementService
        service = ClientManagementService(server)

        # Download config using agent
        content = asyncio.run(service.download_client_config(client.name))

        logger.info(f"Download successful, content_size={len(content) if content else 0}")

        if content:
            response = HttpResponse(content, content_type="application/x-openvpn-profile")
            response["Content-Disposition"] = f'attachment; filename="{client.name}.ovpn"'
            logger.info(f"Returning config file {client.name}.ovpn")
            return response
        else:
            error_msg = "Не удалось скачать конфигурацию: файл не найден на сервере"
            logger.error(error_msg)
            messages.error(request, error_msg)
            return redirect("ovpn_app:client_list")

    except Exception as e:
        error_msg = f"Ошибка при скачивании конфигурации: {str(e)}"
        logger.error(error_msg, exc_info=True)
        messages.error(request, error_msg)
        return redirect("ovpn_app:client_list")


class ConnectionListView(LoginRequiredMixin, ListView):
    """Active connections list"""

    model = VPNConnection
    template_name = "ovpn_app/connections/list.html"
    context_object_name = "connections"
    paginate_by = 50

    def get_queryset(self):
        return VPNConnection.objects.select_related("client", "client__server").order_by(
            "-connected_at"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all servers for filter
        context["servers"] = OpenVPNServer.objects.all()

        # Statistics
        connections = self.get_queryset()
        context.update(
            {
                "total_connections": connections.count(),
                "active_connections": connections.count(),  # All connections in table are considered active
                "servers_with_connections": connections.values("client__server").distinct().count(),
                "total_servers": OpenVPNServer.objects.count(),
                "total_data_transfer": "0 MB",  # Placeholder
            }
        )

        return context


@login_required
def monitoring_view(request):
    """Real-time monitoring page"""
    servers = OpenVPNServer.objects.all()  # Show all servers, not just running
    return render(request, "ovpn_app/monitoring.html", {"servers": servers})


@login_required
def api_server_stats(request, server_id):
    """API endpoint for server statistics"""
    server = get_object_or_404(OpenVPNServer, id=server_id)

    try:
        connections = VPNConnection.objects.filter(client__server=server)

        stats = {
            "server_name": server.name,
            "status": server.status,
            "active_connections": connections.count(),
            "total_clients": server.clients.count(),
            "last_check": server.last_check.isoformat() if server.last_check else None,
            "connections": [],
        }

        for conn in connections:
            stats["connections"].append(
                {
                    "client_name": conn.client.name,
                    "client_ip": conn.client_ip,
                    "virtual_ip": conn.virtual_ip,
                    "connected_at": conn.connected_at.isoformat(),
                    "bytes_received": conn.bytes_received,
                    "bytes_sent": conn.bytes_sent,
                }
            )

        return JsonResponse(stats)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def task_status(request, task_id):
    """Get task status"""
    task = get_object_or_404(ServerTask, task_id=task_id)

    return JsonResponse(
        {
            "task_id": task.task_id,
            "status": task.status,
            "progress": task.progress,
            "task_type": task.get_task_type_display(),
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }
    )
