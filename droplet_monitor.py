import requests
import json
import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class UserInfo:
    """Informações do usuário do Wplace."""
    id: int
    name: str
    email: str
    droplets: int
    charges: Dict[str, Any]
    level: float
    pixels_painted: int

class DropletMonitor:
    """Monitor de droplets com compra automática."""
    
    def __init__(self, cookie: str):
        self.cookie = cookie
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
            'Accept-Encoding': "gzip, deflate, br, zstd",
            'sec-ch-ua-platform': '"Android"',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-mobile': "?1",
            'origin': "https://wplace.live",
            'sec-fetch-site': "same-site",
            'sec-fetch-mode': "cors",
            'sec-fetch-dest': "empty",
            'referer': "https://wplace.live/",
            'accept-language': "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            'priority': "u=1, i",
            'Cookie': cookie
        })
    
    def get_user_info(self) -> Optional[UserInfo]:
        """Obtém informações do usuário."""
        try:
            url = "https://backend.wplace.live/me"
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                user_info = UserInfo(
                    id=data.get('id', 0),
                    name=data.get('name', ''),
                    email=data.get('email', ''),
                    droplets=data.get('droplets', 0),
                    charges=data.get('charges', {}),
                    level=data.get('level', 0.0),
                    pixels_painted=data.get('pixelsPainted', 0)
                )
                
                logger.info(f"Usuário: {user_info.name} | Droplets: {user_info.droplets} | Level: {user_info.level:.2f}")
                return user_info
            else:
                logger.error(f"Erro ao obter informações do usuário: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao obter informações do usuário: {e}")
            return None
    
    def purchase_droplets(self, amount: int = 1) -> bool:
        """Compra droplets automaticamente."""
        try:
            url = "https://backend.wplace.live/purchase"
            
            payload = json.dumps({
                "product": {
                    "id": 80,  # ID do produto droplets
                    "amount": amount
                }
            })
            
            headers = {
                'Content-Type': "text/plain;charset=UTF-8",
                **self.session.headers
            }
            
            response = self.session.post(url, data=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Compra realizada com sucesso! Resposta: {result}")
                return True
            else:
                logger.error(f"❌ Erro na compra: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao realizar compra: {e}")
            return False
    
    def monitor_and_buy_droplets(self, target_droplets: int = 500, check_interval: int = 30) -> None:
        """Monitora droplets e compra automaticamente quando necessário."""
        logger.info(f"🔍 Iniciando monitoramento de droplets (meta: {target_droplets})")
        
        while True:
            try:
                user_info = self.get_user_info()
                
                if user_info is None:
                    logger.warning("⚠️ Não foi possível obter informações do usuário")
                    time.sleep(check_interval)
                    continue
                
                current_droplets = user_info.droplets
                logger.info(f"💰 Droplets atuais: {current_droplets}")
                
                # Verifica se precisa comprar
                if current_droplets < target_droplets:
                    needed = target_droplets - current_droplets
                    logger.info(f"🛒 Preciso comprar {needed} droplets para atingir {target_droplets}")
                    
                    # Calcula quantas compras precisa fazer (cada compra dá 100 droplets)
                    purchases_needed = (needed + 99) // 100  # Arredonda para cima
                    
                    for i in range(purchases_needed):
                        logger.info(f"🛒 Realizando compra {i+1}/{purchases_needed}")
                        
                        if self.purchase_droplets(amount=1):
                            logger.info(f"✅ Compra {i+1} realizada com sucesso!")
                            
                            # Aguarda um pouco entre compras
                            time.sleep(2)
                        else:
                            logger.error(f"❌ Falha na compra {i+1}")
                            break
                    
                    # Verifica se conseguiu comprar
                    time.sleep(5)  # Aguarda atualização
                    new_user_info = self.get_user_info()
                    if new_user_info:
                        logger.info(f"💰 Novos droplets: {new_user_info.droplets}")
                
                else:
                    logger.info(f"✅ Droplets suficientes: {current_droplets} >= {target_droplets}")
                
                # Aguarda próximo check
                logger.info(f"⏰ Próximo check em {check_interval} segundos...")
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                logger.info("⏹️ Monitoramento interrompido pelo usuário")
                break
            except Exception as e:
                logger.error(f"❌ Erro no monitoramento: {e}")
                time.sleep(check_interval)

class AutoDropletManager:
    """Gerenciador automático de droplets integrado ao sistema de pintura."""
    
    def __init__(self, cookie: str):
        self.monitor = DropletMonitor(cookie)
        self.target_droplets = 500
        self.check_interval = 30
        self.is_monitoring = False
    
    def start_monitoring(self, target_droplets: int = 500, check_interval: int = 30):
        """Inicia monitoramento automático."""
        self.target_droplets = target_droplets
        self.check_interval = check_interval
        self.is_monitoring = True
        
        logger.info(f"🚀 Iniciando monitoramento automático de droplets")
        logger.info(f"   Meta: {target_droplets} droplets")
        logger.info(f"   Check a cada: {check_interval} segundos")
        
        self.monitor.monitor_and_buy_droplets(target_droplets, check_interval)
    
    def check_and_buy_if_needed(self) -> bool:
        """Verifica e compra droplets se necessário (para uso durante pintura)."""
        user_info = self.monitor.get_user_info()
        
        if user_info and user_info.droplets < self.target_droplets:
            logger.warning(f"⚠️ Droplets baixos: {user_info.droplets} < {self.target_droplets}")
            logger.info("🛒 Tentando comprar droplets...")
            
            return self.monitor.purchase_droplets()
        
        return True
    
    def get_current_droplets(self) -> int:
        """Obtém quantidade atual de droplets."""
        user_info = self.monitor.get_user_info()
        return user_info.droplets if user_info else 0

def test_droplet_system():
    """Testa o sistema de droplets."""
    print("🧪 TESTE DO SISTEMA DE DROPLETS")
    print("=" * 50)
    
    # Cookie de exemplo (substitua pelo seu)
    test_cookie = "s=5cYtW1Zfh2wRSw1qoPG4Jg%3D%3D; cf_clearance=J2xpm4zVIs6bqW0icKiU9rprAyZkvGnVd.KgA.aBgoA-1754582945-1.2.1.1-WgvyQB7BwcBAzcCumwN.rXEyXnMnsNiXop_LgVxnx97f5tn3I0U5B31UqNDnmhlgz_Yz0zeRWZUdanuZRN6ljDhLdqT_X7huEIa1lmjWRmiZ_rltGoUdIFWDPSMwbfF6PH_cE1aD9_dQQKPb5zBuIn7fOHBSQ1MXV3UYW.zfF0Ydjfjnaoi3lKZwzBRXYAIX2b8Wkz4wvIQdQGopGWJeLA1Zc6RHkfgHHeRzeAs1Mzc"
    
    manager = AutoDropletManager(test_cookie)
    
    # Testa obtenção de informações
    print("🔍 Testando obtenção de informações do usuário...")
    user_info = manager.monitor.get_user_info()
    
    if user_info:
        print(f"✅ Usuário: {user_info.name}")
        print(f"✅ Email: {user_info.email}")
        print(f"✅ Droplets: {user_info.droplets}")
        print(f"✅ Level: {user_info.level:.2f}")
        print(f"✅ Pixels pintados: {user_info.pixels_painted}")
        
        # Testa compra se necessário
        if user_info.droplets < 500:
            print(f"\n🛒 Droplets baixos ({user_info.droplets} < 500)")
            print("🛒 Testando compra automática...")
            
            success = manager.monitor.purchase_droplets()
            if success:
                print("✅ Compra realizada com sucesso!")
            else:
                print("❌ Falha na compra")
        else:
            print(f"\n✅ Droplets suficientes: {user_info.droplets} >= 500")
    else:
        print("❌ Falha ao obter informações do usuário")

if __name__ == "__main__":
    # Configuração de logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    test_droplet_system()