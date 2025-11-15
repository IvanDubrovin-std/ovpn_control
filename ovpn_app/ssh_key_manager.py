"""
SSH Key Management Module

Автоматическая генерация SSH ключей и их установка на удаленные серверы.
Использует cryptography для генерации ключей и asyncssh для установки.
"""

import logging
from typing import Optional, Tuple

import asyncssh
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

logger = logging.getLogger(__name__)


class SSHKeyType:
    """Типы SSH ключей"""

    RSA = "rsa"
    ED25519 = "ed25519"


class SSHKeyManager:
    """Менеджер для генерации и установки SSH ключей"""

    def __init__(self, key_type: str = SSHKeyType.ED25519, rsa_key_size: int = 4096):
        """
        Инициализация менеджера

        Args:
            key_type: Тип ключа (rsa или ed25519)
            rsa_key_size: Размер RSA ключа (по умолчанию 4096)
        """
        self.key_type = key_type
        self.rsa_key_size = rsa_key_size

    def generate_key_pair(self) -> Tuple[str, str]:
        """
        Генерирует пару SSH ключей (приватный и публичный)

        Returns:
            Tuple[str, str]: (private_key_pem, public_key_openssh)
        """
        logger.info(f"Generating {self.key_type} SSH key pair...")

        if self.key_type == SSHKeyType.RSA:
            return self._generate_rsa_key()
        elif self.key_type == SSHKeyType.ED25519:
            return self._generate_ed25519_key()
        else:
            raise ValueError(f"Unsupported key type: {self.key_type}")

    def _generate_rsa_key(self) -> Tuple[str, str]:
        """Генерирует RSA ключ"""
        # Генерация приватного ключа
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=self.rsa_key_size, backend=default_backend()
        )

        # Сериализация приватного ключа в PEM формат
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        # Получение публичного ключа
        public_key = private_key.public_key()
        public_openssh = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH, format=serialization.PublicFormat.OpenSSH
        ).decode("utf-8")

        logger.info(f"Generated RSA-{self.rsa_key_size} key pair")
        return private_pem, public_openssh

    def _generate_ed25519_key(self) -> Tuple[str, str]:
        """Генерирует ED25519 ключ"""
        # Генерация приватного ключа
        private_key = ed25519.Ed25519PrivateKey.generate()

        # Сериализация приватного ключа в PEM формат
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        # Получение публичного ключа
        public_key = private_key.public_key()
        public_openssh = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH, format=serialization.PublicFormat.OpenSSH
        ).decode("utf-8")

        logger.info("Generated ED25519 key pair")
        return private_pem, public_openssh

    async def install_public_key(
        self, host: str, username: str, password: str, public_key: str, port: int = 22
    ) -> bool:
        """
        Устанавливает публичный ключ на удаленный сервер

        Args:
            host: Адрес сервера
            username: Имя пользователя
            password: Пароль для подключения
            public_key: Публичный ключ в OpenSSH формате
            port: SSH порт

        Returns:
            bool: True если успешно установлен
        """
        logger.info(f"Installing public key on {host}...")

        try:
            # Подключаемся к серверу с паролем
            async with asyncssh.connect(
                host, port=port, username=username, password=password, known_hosts=None
            ) as conn:
                # Создаем директорию .ssh если её нет
                await conn.run("mkdir -p ~/.ssh")
                await conn.run("chmod 700 ~/.ssh")

                # Добавляем публичный ключ в authorized_keys
                # Используем grep для проверки, не добавлен ли уже этот ключ
                public_key_clean = public_key.strip()

                # Проверяем существование файла
                result = await conn.run("test -f ~/.ssh/authorized_keys", check=False)

                if result.exit_status != 0:
                    # Файл не существует, создаем
                    await conn.run(f'echo "{public_key_clean}" > ~/.ssh/authorized_keys')
                    logger.info("Created new authorized_keys file")
                else:
                    # Файл существует, проверяем наличие ключа
                    check_result = await conn.run(
                        f'grep -F "{public_key_clean}" ~/.ssh/authorized_keys', check=False
                    )

                    if check_result.exit_status != 0:
                        # Ключа нет, добавляем
                        await conn.run(f'echo "{public_key_clean}" >> ~/.ssh/authorized_keys')
                        logger.info("Appended key to authorized_keys")
                    else:
                        logger.info("Key already exists in authorized_keys")

                # Устанавливаем правильные права доступа
                await conn.run("chmod 600 ~/.ssh/authorized_keys")

                logger.info(f"✓ Public key successfully installed on {host}")
                return True

        except asyncssh.Error as e:
            logger.error(f"Failed to install public key on {host}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error installing public key: {e}")
            return False

    async def generate_and_install(
        self, host: str, username: str, password: str, port: int = 22
    ) -> Optional[Tuple[str, str, bool]]:
        """
        Генерирует ключи и устанавливает публичный ключ на сервер

        Args:
            host: Адрес сервера
            username: Имя пользователя
            password: Пароль для подключения
            port: SSH порт

        Returns:
            Optional[Tuple[str, str, bool]]: (private_key, public_key, success) или None
        """
        try:
            # Генерируем ключи
            private_key, public_key = self.generate_key_pair()

            # Устанавливаем публичный ключ на сервер
            success = await self.install_public_key(
                host=host, username=username, password=password, public_key=public_key, port=port
            )

            if success:
                logger.info(f"✓ SSH key pair generated and installed for {username}@{host}")
                return private_key, public_key, True
            else:
                logger.error("Failed to install public key")
                return private_key, public_key, False

        except Exception as e:
            logger.error(f"Failed to generate and install SSH key: {e}")
            return None


def sync_generate_and_install(
    host: str, username: str, password: str, port: int = 22, key_type: str = SSHKeyType.ED25519
) -> Optional[Tuple[str, str, bool]]:
    """
    Синхронная обертка для generate_and_install

    Args:
        host: Адрес сервера
        username: Имя пользователя
        password: Пароль для подключения
        port: SSH порт
        key_type: Тип ключа (rsa или ed25519)

    Returns:
        Optional[Tuple[str, str, bool]]: (private_key, public_key, success) или None
    """
    import asyncio

    manager = SSHKeyManager(key_type=key_type)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(manager.generate_and_install(host, username, password, port))
