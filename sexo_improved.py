import json
import time
import math
import os
import signal
import threading
import logging
import colorsys
from PIL import Image
import requests
from typing import Tuple, Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

# Sistema de droplets integrado
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

class AutoDropletManager:
    """Gerenciador automático de droplets integrado ao sistema de pintura."""
    
    def __init__(self, cookie: str):
        self.monitor = DropletMonitor(cookie)
        self.target_droplets = 500
        self.check_interval = 30
        self.is_monitoring = False
    
    def check_and_buy_if_needed(self) -> bool:
        """Verifica e compra droplets se necessário."""
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

# Sistema de detecção de cores compatível com Termux
class TermuxColorDetector:
    """Sistema de detecção de cores otimizado para Termux."""
    
    def __init__(self):
        self.color_cache = {}
    
    def rgb_to_hsv(self, rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """Converte RGB para HSV."""
        r, g, b = rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0
        return colorsys.rgb_to_hsv(r, g, b)
    
    def find_best_color_match(self, target_rgb: Tuple[int, int, int], 
                             palette: Dict[Tuple[int, int, int], int]) -> int:
        """Encontra a melhor correspondência de cor usando múltiplos métodos."""
        
        # Cache para evitar recálculos
        cache_key = (target_rgb, tuple(sorted(palette.keys())))
        if cache_key in self.color_cache:
            return self.color_cache[cache_key]
        
        # Método 1: Correspondência exata
        if target_rgb in palette:
            self.color_cache[cache_key] = palette[target_rgb]
            return palette[target_rgb]
        
        # Método 2: Distância Euclidiana em RGB
        min_distance_rgb = float('inf')
        best_index_rgb = 0
        
        # Método 3: Distância em HSV (mais perceptualmente precisa)
        min_distance_hsv = float('inf')
        best_index_hsv = 0
        
        target_hsv = self.rgb_to_hsv(target_rgb)
        
        for palette_rgb, index in palette.items():
            # Distância RGB
            rgb_distance = sum((a - b) ** 2 for a, b in zip(target_rgb, palette_rgb))
            if rgb_distance < min_distance_rgb:
                min_distance_rgb = rgb_distance
                best_index_rgb = index
            
            # Distância HSV (mais precisa para percepção humana)
            palette_hsv = self.rgb_to_hsv(palette_rgb)
            
            # Normaliza H (hue) para comparação circular
            h_diff = min(abs(target_hsv[0] - palette_hsv[0]), 
                        1 - abs(target_hsv[0] - palette_hsv[0]))
            
            # Distância HSV ponderada
            hsv_distance = (h_diff * 2) ** 2 + (target_hsv[1] - palette_hsv[1]) ** 2 + (target_hsv[2] - palette_hsv[2]) ** 2
            
            if hsv_distance < min_distance_hsv:
                min_distance_hsv = hsv_distance
                best_index_hsv = index
        
        # Escolhe o melhor resultado (HSV é geralmente mais preciso)
        best_index = best_index_hsv if min_distance_hsv < min_distance_rgb * 0.8 else best_index_rgb
        
        self.color_cache[cache_key] = best_index
        return best_index

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('wplace_painter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Paleta de cores do Wplace.live
COLOR_PALETTE = {
    (0, 0, 0): 0,        # Black
    (60, 60, 60): 1,     # Dark Gray
    (120, 120, 120): 2,  # Gray
    (210, 210, 210): 3,  # Light Gray
    (255, 255, 255): 4,  # White
    (96, 0, 24): 5,      # Deep Red
    (237, 28, 36): 6,    # Red
    (255, 127, 39): 7,   # Orange
    (246, 170, 9): 8,    # Gold
    (249, 221, 59): 9,   # Yellow
    (255, 250, 188): 10, # Light Yellow
    (14, 185, 104): 11,  # Dark Green
    (19, 230, 123): 12,  # Green
    (135, 255, 94): 13,  # Light Green
    (12, 129, 110): 14,  # Dark Teal
    (16, 174, 166): 15,  # Teal
    (19, 225, 190): 16,  # Light Teal
    (40, 80, 158): 17,   # Dark Blue
    (64, 147, 228): 18,  # Blue
    (96, 247, 242): 19,  # Cyan
    (107, 80, 246): 20,  # Indigo
    (153, 177, 251): 21, # Light Indigo
    (120, 12, 153): 22,  # Dark Purple
    (170, 56, 185): 23,  # Purple
    (224, 159, 249): 24, # Light Purple
    (203, 0, 122): 25,   # Dark Pink
    (236, 31, 128): 26,  # Pink
    (243, 141, 169): 27, # Light Pink
    (104, 70, 52): 28,   # Dark Brown
    (149, 104, 42): 29,  # Brown
    (248, 178, 119): 30  # Beige
}

# Criar mapa reverso para acesso rápido
COLOR_MAP = {color: index for color, index in COLOR_PALETTE.items()}

@dataclass
class WplaceCoordinate:
    """Sistema de coordenadas do Wplace.live com tile e posição dentro do tile."""
    tl_x: int  # Tile X
    tl_y: int  # Tile Y  
    px_x: int  # Pixel X dentro do tile
    px_y: int  # Pixel Y dentro do tile
    
    def move(self, direction: str, tile_size: int = 1000) -> 'WplaceCoordinate':
        """Aplica movimento no sistema de coordenadas do Wplace."""
        moves = {
            "up": (0, -1),
            "down": (0, 1), 
            "left": (-1, 0),
            "right": (1, 0),
        }
        
        if direction not in moves:
            raise ValueError(f"Direção inválida: {direction}")
        
        dx, dy = moves[direction]
        new_px_x = self.px_x + dx
        new_px_y = self.px_y + dy
        new_tl_x = self.tl_x
        new_tl_y = self.tl_y
        
        # Ajusta tile se pixel sair dos limites
        if new_px_x >= tile_size:
            new_px_x = 0
            new_tl_x += 1
        elif new_px_x < 0:
            new_px_x = tile_size - 1
            new_tl_x -= 1
            
        if new_px_y >= tile_size:
            new_px_y = 0
            new_tl_y += 1
        elif new_px_y < 0:
            new_px_y = tile_size - 1
            new_tl_y -= 1
            
        return WplaceCoordinate(new_tl_x, new_tl_y, new_px_x, new_px_y)
    
    def to_absolute(self, tile_size: int = 1000) -> Tuple[int, int]:
        """Converte para coordenadas absolutas."""
        abs_x = self.tl_x * tile_size + self.px_x
        abs_y = self.tl_y * tile_size + self.px_y
        return abs_x, abs_y
    
    @classmethod
    def from_absolute(cls, abs_x: int, abs_y: int, tile_size: int = 1000) -> 'WplaceCoordinate':
        """Cria coordenada do Wplace a partir de coordenadas absolutas."""
        tl_x = abs_x // tile_size
        tl_y = abs_y // tile_size
        px_x = abs_x % tile_size
        px_y = abs_y % tile_size
        return cls(tl_x, tl_y, px_x, px_y)
    
    def is_valid(self, max_tile: int = 5000, tile_size: int = 1000) -> bool:
        """Verifica se as coordenadas são válidas."""
        return (0 <= self.tl_x <= max_tile and 0 <= self.tl_y <= max_tile and
                0 <= self.px_x < tile_size and 0 <= self.px_y < tile_size)

class CookieManager:
    """Gerenciador de cookies com salvamento automático."""
    
    def __init__(self, cookie_file: str = "cookies.json"):
        self.cookie_file = cookie_file
        self.cookies = self.load_cookies()
    
    def load_cookies(self) -> List[str]:
        """Carrega cookies do arquivo JSON."""
        try:
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('cookies', [])
            return []
        except Exception as e:
            logger.error(f"Erro ao carregar cookies: {e}")
            return []
    
    def save_cookies(self):
        """Salva cookies no arquivo JSON."""
        try:
            data = {
                'cookies': self.cookies,
                'last_updated': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Cookies salvos em {self.cookie_file}")
        except Exception as e:
            logger.error(f"Erro ao salvar cookies: {e}")
    
    def add_cookie(self, cookie: str):
        """Adiciona um novo cookie."""
        if cookie and cookie not in self.cookies:
            self.cookies.append(cookie)
            self.save_cookies()
            logger.info(f"Cookie adicionado. Total: {len(self.cookies)}")
    
    def remove_cookie(self, index: int):
        """Remove cookie por índice."""
        if 0 <= index < len(self.cookies):
            removed = self.cookies.pop(index)
            self.save_cookies()
            logger.info(f"Cookie removido: {removed[:50]}...")
    
    def list_cookies(self):
        """Lista todos os cookies."""
        if not self.cookies:
            print("📋 Nenhum cookie salvo.")
            return
        
        print("📋 Cookies salvos:")
        for i, cookie in enumerate(self.cookies):
            preview = cookie[:50] + "..." if len(cookie) > 50 else cookie
            print(f"   [{i}] {preview}")
    
    def get_cookies(self) -> List[str]:
        """Retorna lista de cookies."""
        return self.cookies.copy()

class ProgressManager:
    """Gerenciador de progresso com salvamento automático."""
    
    def __init__(self, backup_file: str = "progress_backup.json"):
        self.backup_file = backup_file
        self.progress_data = {}
        self.lock = threading.Lock()
    
    def save_progress(self, image_path: str, start_coord: WplaceCoordinate, 
                     completed_pixels: List[int], total_pixels: int, 
                     pixel_map: Dict):
        """Salva progresso atual."""
        with self.lock:
            self.progress_data = {
                'image_path': image_path,
                'start_coordinate': asdict(start_coord),
                'completed_pixels': completed_pixels,
                'total_pixels': total_pixels,
                'pixel_map': pixel_map,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'completion_percentage': len(completed_pixels) / total_pixels * 100 if total_pixels > 0 else 0
            }
            
            try:
                with open(self.backup_file, 'w', encoding='utf-8') as f:
                    json.dump(self.progress_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Erro ao salvar progresso: {e}")
    
    def load_progress(self) -> Optional[Dict]:
        """Carrega progresso salvo."""
        try:
            if os.path.exists(self.backup_file):
                with open(self.backup_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Erro ao carregar progresso: {e}")
            return None
    
    def has_backup(self) -> bool:
        """Verifica se existe backup."""
        return os.path.exists(self.backup_file)
    
    def clear_backup(self):
        """Remove arquivo de backup."""
        try:
            if os.path.exists(self.backup_file):
                os.remove(self.backup_file)
                logger.info("Backup removido")
        except Exception as e:
            logger.error(f"Erro ao remover backup: {e}")

class WplacePixelPainter:
    """Sistema de pintura para Wplace.live usando o sistema de tiles."""
    
    def __init__(self, cookie: str, painter_id: int, delay: float = 1.0):
        self.cookie = cookie
        self.painter_id = painter_id
        self.delay = delay
        self.session = requests.Session()
        self.painted_count = 0
        
        # Adicionar gerenciador de droplets
        self.droplet_manager = AutoDropletManager(cookie)
        
        self.session.headers.update({
            'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36 EdgA/139.0.0.0",
            'Accept-Encoding': "gzip, deflate, br, zstd",
            'Content-Type': "text/plain;charset=UTF-8",
            'sec-ch-ua-platform': '"Android"',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
            'sec-ch-ua-mobile': "?1",
            'origin': "https://wplace.live",
            'sec-fetch-site': "same-site",
            'sec-fetch-mode': "cors",
            'sec-fetch-dest': "empty",
            'referer': "https://wplace.live/",
            'accept-language': "pt-BR,pt;q=0.9",
            'priority': "u=1, i",
            'Cookie': cookie
        })
    
    def rgb_to_color_index(self, rgb: Tuple[int, int, int]) -> int:
        """Converte RGB para índice da paleta usando sistema avançado."""
        
        # Usa sistema avançado de detecção de cores
        detector = TermuxColorDetector()
        return detector.find_best_color_match(rgb, COLOR_PALETTE)
    
    def paint_pixel(self, coord: WplaceCoordinate, color_index: int) -> bool:
        """Pinta um pixel no Wplace.live com tratamento de erro 403 e monitoramento de droplets."""
        if not coord.is_valid():
            logger.error(f"[P{self.painter_id}] Coordenada inválida: Tl({coord.tl_x},{coord.tl_y}) Px({coord.px_x},{coord.px_y})")
            return False
        
        url = f"https://backend.wplace.live/s0/pixel/{coord.tl_x}/{coord.tl_y}"
        payload = json.dumps({"colors": [color_index], "coords": [coord.px_x, coord.px_y]})
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                time.sleep(self.delay)
                response = self.session.post(url, data=payload)
                
                if response.status_code == 200:
                    abs_x, abs_y = coord.to_absolute()
                    self.painted_count += 1
                    logger.info(f"[P{self.painter_id}] Pintado Tl({coord.tl_x},{coord.tl_y}) Px({coord.px_x},{coord.px_y}) -> Abs({abs_x},{abs_y}) Cor:{color_index}")
                    return True
                    
                elif response.status_code == 403:
                    try:
                        error_data = response.json()
                        charges = error_data.get('charges', 0)
                        logger.warning(f"[P{self.painter_id}] Sem tinta! Charges: {charges:.3f}")
                        
                        # Verifica droplets antes de pausar
                        current_droplets = self.droplet_manager.get_current_droplets()
                        logger.info(f"[P{self.painter_id}] Droplets atuais: {current_droplets}")
                        
                        if current_droplets < 500:
                            logger.info(f"[P{self.painter_id}] Droplets baixos! Tentando comprar...")
                            if self.droplet_manager.check_and_buy_if_needed():
                                logger.info(f"[P{self.painter_id}] ✅ Droplets comprados com sucesso!")
                                # Continua imediatamente após compra
                                continue
                        
                        logger.info(f"[P{self.painter_id}] Pausando 30 segundos para recarregar tinta...")
                        
                        # Countdown de 30 segundos
                        for i in range(30, 0, -1):
                            print(f"\r⏱️ [P{self.painter_id}] Aguardando: {i}s restantes...", end="", flush=True)
                            time.sleep(1)
                        print(f"\n🔄 [P{self.painter_id}] Tentando novamente...")
                        continue  # Tenta novamente após a pausa
                        
                    except json.JSONDecodeError:
                        logger.error(f"[P{self.painter_id}] Erro 403 sem dados JSON: {response.text}")
                        return False
                        
                else:
                    logger.error(f"[P{self.painter_id}] Erro HTTP {response.status_code}: {response.text}")
                    return False
                    
            except requests.RequestException as e:
                logger.error(f"[P{self.painter_id}] Erro de rede: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"[P{self.painter_id}] Tentativa {attempt + 2}/{max_retries} em 5 segundos...")
                    time.sleep(5)
                else:
                    return False
        
        logger.error(f"[P{self.painter_id}] Falha após {max_retries} tentativas")
        return False

class MultiPainterCoordinator:
    """Coordenador para múltiplos painters trabalharem em conjunto."""
    
    def __init__(self, cookies: List[str], delay: float = 1.0):
        self.cookies = cookies
        self.delay = delay
        self.painters = []
        self.stop_event = threading.Event()
        self.progress_manager = ProgressManager()
        self.shared_lock = threading.Lock()
        
        # Criar painters
        for i, cookie in enumerate(cookies):
            painter = WplacePixelPainter(cookie, i + 1, delay)
            self.painters.append(painter)
        
        logger.info(f"Coordenador inicializado com {len(self.painters)} painters")
    
    def distribute_work(self, paint_sequence: List[Tuple[WplaceCoordinate, int]], 
                       num_painters: int) -> List[List[Tuple[WplaceCoordinate, int]]]:
        """Distribui trabalho entre os painters evitando conflitos."""
        chunks = []
        chunk_size = len(paint_sequence) // num_painters
        
        for i in range(num_painters):
            start_idx = i * chunk_size
            if i == num_painters - 1:  # Último painter pega o resto
                end_idx = len(paint_sequence)
            else:
                end_idx = (i + 1) * chunk_size
            
            chunks.append(paint_sequence[start_idx:end_idx])
        
        return chunks
    
    def paint_chunk(self, painter: WplacePixelPainter, chunk: List[Tuple[WplaceCoordinate, int]], 
                   completed_pixels: List[int], pixel_map: Dict, chunk_id: int) -> int:
        """Pinta um pedaço da imagem com um painter específico."""
        successful_paints = 0
        
        for pixel_idx, (coord, color_index) in enumerate(chunk):
            if self.stop_event.is_set():
                break
                
            if not coord.is_valid():
                continue
            
            success = painter.paint_pixel(coord, color_index)
            
            if success:
                successful_paints += 1
                abs_x, abs_y = coord.to_absolute()
                
                # Thread-safe update com lock
                with self.shared_lock:
                    global_idx = chunk_id * len(chunk) + pixel_idx
                    completed_pixels.append(global_idx)
                    pixel_map[f"Tl({coord.tl_x},{coord.tl_y})_Px({coord.px_x},{coord.px_y})"] = {
                        "color_index": color_index,
                        "absolute_coords": [abs_x, abs_y],
                        "painted_at": time.strftime("%H:%M:%S"),
                        "painter_id": painter.painter_id
                    }
        
        return successful_paints

class WplaceImageProcessor:
    """Processador de imagens para Wplace.live com suporte multi-painter."""
    
    def __init__(self, coordinator: MultiPainterCoordinator):
        self.coordinator = coordinator
    
    def load_image(self, image_path: str) -> Optional[Image.Image]:
        """Carrega e valida imagem."""
        try:
            img = Image.open(image_path).convert("RGBA")
            logger.info(f"Imagem carregada: {img.size[0]}x{img.size[1]} pixels")
            return img
        except FileNotFoundError:
            logger.error(f"Imagem '{image_path}' não encontrada.")
            return None
        except Exception as e:
            logger.error(f"Erro ao carregar imagem: {str(e)}")
            return None
    
    def generate_paint_sequence(self, img: Image.Image, 
                               start_coord: WplaceCoordinate) -> List[Tuple[WplaceCoordinate, int]]:
        """Gera sequência de pixels para pintar em espiral começando pelo centro da imagem."""
        width, height = img.size
        pixels = img.load()
        
        logger.info(f"Iniciando pela coordenada: Tl({start_coord.tl_x},{start_coord.tl_y}) Px({start_coord.px_x},{start_coord.px_y})")
        
        # Coletar todos os pixels válidos primeiro
        valid_pixels = []
        
        for img_y in range(height):
            for img_x in range(width):
                r, g, b, a = pixels[img_x, img_y]
                
                # Ignora apenas pixels transparentes
                if a == 0:
                    continue
                
                # Calcula coordenada do Wplace para este pixel da imagem
                current_coord = WplaceCoordinate(
                    start_coord.tl_x,
                    start_coord.tl_y,
                    start_coord.px_x + img_x,
                    start_coord.px_y + img_y
                )
                
                # Ajusta coordenada se ultrapassar os limites do tile
                if current_coord.px_x >= 1000:
                    current_coord.tl_x += current_coord.px_x // 1000
                    current_coord.px_x %= 1000
                if current_coord.px_y >= 1000:
                    current_coord.tl_y += current_coord.px_y // 1000
                    current_coord.px_y %= 1000
                
                # Mapeia cor
                if len(self.coordinator.painters) > 0:
                    color_index = self.coordinator.painters[0].rgb_to_color_index((r, g, b))
                    
                    # Armazena pixel com informações extras para ordenação em espiral
                    valid_pixels.append({
                        'coord': current_coord,
                        'color': color_index,
                        'img_x': img_x,
                        'img_y': img_y
                    })
        
        # Ordena pixels em forma de espiral começando do centro
        center_x = width // 2
        center_y = height // 2
        
        def spiral_order(pixel):
            x = pixel['img_x']
            y = pixel['img_y']
            
            # Calcula distância do centro
            dx = x - center_x
            dy = y - center_y
            distance = math.sqrt(dx * dx + dy * dy)
            
            # Calcula ângulo para ordenar em espiral
            angle = math.atan2(dy, dx)
            
            # Converte ângulo para 0-2π para ordenação consistente
            if angle < 0:
                angle += 2 * math.pi
            
            # Ordena primeiro por distância (círculos concêntricos), depois por ângulo (espiral)
            return (distance, angle)
        
        # Ordena por distância do centro em espiral
        valid_pixels.sort(key=spiral_order)
        
        # Converte para formato final
        paint_sequence = [(pixel['coord'], pixel['color']) for pixel in valid_pixels]
        
        logger.info(f"Sequência em espiral gerada: {len(paint_sequence)} pixels para pintar (centro → bordas)")
        logger.info(f"Centro da imagem: ({center_x}, {center_y})")
        
        return paint_sequence
    
    def paint_image(self, image_path: str, start_coord: WplaceCoordinate, 
                   output_json: Optional[str] = None, resume: bool = False) -> bool:
        """Processo principal de pintura da imagem com múltiplos painters."""
        print("🎨" + "="*60)
        print("🎨 INICIANDO PINTURA MULTI-PAINTER NO WPLACE.LIVE")
        print("🎨" + "="*60)
        
        # Verificar se deve continuar de onde parou
        if resume and self.coordinator.progress_manager.has_backup():
            return self.resume_painting(output_json)
        
        # Carrega imagem
        img = self.load_image(image_path)
        if img is None:
            return False
        
        # Gera sequência de pintura
        paint_sequence = self.generate_paint_sequence(img, start_coord)
        if not paint_sequence:
            logger.error("Nenhum pixel válido para pintar")
            return False
        
        # Configurar tratamento de interrupção
        completed_pixels = []
        pixel_map = {}
        
        def signal_handler(signum, frame):
            logger.info(f"Recebido sinal de interrupção ({signum})")
            self.coordinator.stop_event.set()
            self.coordinator.progress_manager.save_progress(
                image_path, start_coord, completed_pixels, 
                len(paint_sequence), pixel_map
            )
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        return self._execute_painting(paint_sequence, image_path, start_coord, 
                                    img, completed_pixels, pixel_map, output_json)
    
    def resume_painting(self, output_json: Optional[str] = None) -> bool:
        """Continua pintura de onde parou."""
        progress = self.coordinator.progress_manager.load_progress()
        if not progress:
            logger.error("Não foi possível carregar progresso")
            return False
        
        logger.info("Continuando pintura de onde parou...")
        logger.info(f"Progresso anterior: {progress['completion_percentage']:.1f}%")
        
        # Recarregar imagem
        img = self.load_image(progress['image_path'])
        if img is None:
            return False
        
        # Recriar coordenada inicial
        coord_data = progress['start_coordinate']
        start_coord = WplaceCoordinate(
            coord_data['tl_x'], coord_data['tl_y'],
            coord_data['px_x'], coord_data['px_y']
        )
        
        # Gerar sequência completa
        full_sequence = self.generate_paint_sequence(img, start_coord)
        
        # Filtrar pixels já pintados
        completed_set = set(progress['completed_pixels'])
        remaining_sequence = [
            pixel for i, pixel in enumerate(full_sequence) 
            if i not in completed_set
        ]
        
        logger.info(f"Restam {len(remaining_sequence)} pixels para pintar")
        
        completed_pixels = progress['completed_pixels'].copy()
        pixel_map = progress['pixel_map'].copy()
        
        return self._execute_painting(remaining_sequence, progress['image_path'], 
                                    start_coord, img, completed_pixels, pixel_map, output_json)
    
    def _execute_painting(self, paint_sequence: List[Tuple[WplaceCoordinate, int]], 
                         image_path: str, start_coord: WplaceCoordinate, img: Image.Image,
                         completed_pixels: List[int], pixel_map: Dict, 
                         output_json: Optional[str] = None) -> bool:
        """Executa a pintura com múltiplos painters."""
        
        num_painters = len(self.coordinator.painters)
        logger.info(f"Usando {num_painters} painters para {len(paint_sequence)} pixels...")
        
        # Distribuir trabalho
        work_chunks = self.coordinator.distribute_work(paint_sequence, num_painters)
        
        # Executar pintura com ThreadPoolExecutor
        total_successful = 0
        
        try:
            with ThreadPoolExecutor(max_workers=num_painters) as executor:
                # Submeter tarefas
                futures = []
                for i, (painter, chunk) in enumerate(zip(self.coordinator.painters, work_chunks)):
                    if chunk:  # Só submete se o chunk não estiver vazio
                        future = executor.submit(
                            self.coordinator.paint_chunk, 
                            painter, chunk, completed_pixels, pixel_map, i
                        )
                        futures.append(future)
                
                # Acompanhar progresso
                start_time = time.time()
                while futures:
                    # Verificar futures concluídos
                    for future in as_completed(futures, timeout=5):
                        if future in futures:
                            futures.remove(future)
                            try:
                                result = future.result()
                                total_successful += result
                            except Exception as e:
                                logger.error(f"Erro em painter: {e}")
                    
                    # Salvar progresso periodicamente
                    elapsed = time.time() - start_time
                    if elapsed > 30:  # A cada 30 segundos
                        self.coordinator.progress_manager.save_progress(
                            image_path, start_coord, completed_pixels,
                            len(paint_sequence) + len(completed_pixels), pixel_map
                        )
                        start_time = time.time()
                    
                    # Mostrar progresso
                    if len(completed_pixels) > 0:
                        progress = len(completed_pixels) / (len(paint_sequence) + len(completed_pixels)) * 100
                        print(f"📊 Progresso: {progress:.1f}% - Sucessos: {total_successful}")
        
        except KeyboardInterrupt:
            logger.info("Interrompido pelo usuário")
            self.coordinator.stop_event.set()
            self.coordinator.progress_manager.save_progress(
                image_path, start_coord, completed_pixels,
                len(paint_sequence) + len(completed_pixels), pixel_map
            )
            return False
        
        # Salva JSON final
        if output_json:
            self.save_result_json(image_path, img, start_coord, pixel_map, output_json)
        
        # Limpar backup se concluído com sucesso
        self.coordinator.progress_manager.clear_backup()
        
        print("-" * 60)
        print(f"✅ PINTURA CONCLUÍDA: {total_successful} pixels pintados")
        print(f"📊 Painters ativos: {num_painters}")
        for i, painter in enumerate(self.coordinator.painters):
            print(f"   Painter {i+1}: {painter.painted_count} pixels")
        
        return total_successful > 0
    
    def save_result_json(self, image_path: str, img: Image.Image, 
                        start_coord: WplaceCoordinate, pixel_map: Dict, 
                        output_path: str):
        """Salva resultado em JSON."""
        try:
            abs_x, abs_y = start_coord.to_absolute()
            result_data = {
                "metadata": {
                    "image_file": image_path,
                    "dimensions": {"width": img.size[0], "height": img.size[1]},
                    "start_coordinate": {
                        "tile": {"x": start_coord.tl_x, "y": start_coord.tl_y},
                        "pixel": {"x": start_coord.px_x, "y": start_coord.px_y},
                        "absolute": {"x": abs_x, "y": abs_y}
                    },
                    "painted_pixels": len(pixel_map),
                    "num_painters": len(self.coordinator.painters),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "painted_pixels": pixel_map
            }
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=2)
            
            logger.info(f"Resultado salvo em: {output_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar JSON: {str(e)}")

def manage_cookies():
    """Interface para gerenciar cookies."""
    cookie_manager = CookieManager()
    
    while True:
        print("\n🍪" + "="*40)
        print("🍪 GERENCIADOR DE COOKIES")
        print("🍪" + "="*40)
        print("1. Listar cookies")
        print("2. Adicionar cookie")
        print("3. Remover cookie")
        print("4. Voltar ao menu principal")
        
        choice = input("\nEscolha uma opção (1-4): ").strip()
        
        if choice == "1":
            cookie_manager.list_cookies()
            
        elif choice == "2":
            cookie = input("\n🍪 Cole o cookie completo: ").strip()
            if cookie:
                cookie_manager.add_cookie(cookie)
            else:
                print("❌ Cookie vazio não foi adicionado")
                
        elif choice == "3":
            cookie_manager.list_cookies()
            if cookie_manager.cookies:
                try:
                    index = int(input("\nÍndice do cookie para remover: "))
                    cookie_manager.remove_cookie(index)
                except (ValueError, IndexError):
                    print("❌ Índice inválido")
                    
        elif choice == "4":
            break
            
        else:
            print("❌ Opção inválida")

def main():
    """Interface principal do programa."""
    print("🎨" + "="*50)
    print("🎨 WPLACE.LIVE MULTI-PAINTER")
    print("🎨" + "="*50)
    
    cookie_manager = CookieManager()
    progress_manager = ProgressManager()
    
    while True:
        print("\n🎮 MENU PRINCIPAL:")
        print("1. Iniciar pintura")
        print("2. Continuar pintura (de onde parou)")
        print("3. Gerenciar cookies")
        print("4. Verificar progresso salvo")
        print("5. Sair")
        
        choice = input("\nEscolha uma opção (1-5): ").strip()
        
        if choice == "1":
            start_new_painting(cookie_manager)
            
        elif choice == "2":
            resume_painting(cookie_manager, progress_manager)
            
        elif choice == "3":
            manage_cookies()
            
        elif choice == "4":
            check_saved_progress(progress_manager)
            
        elif choice == "5":
            print("👋 Saindo...")
            break
            
        else:
            print("❌ Opção inválida")

def start_new_painting(cookie_manager: CookieManager):
    """Inicia uma nova pintura."""
    cookies = cookie_manager.get_cookies()
    
    if not cookies:
        print("❌ Nenhum cookie salvo! Use o gerenciador de cookies primeiro.")
        return
    
    print(f"\n📋 {len(cookies)} cookies disponíveis")
    
    # Seleção de quantos cookies usar
    max_painters = len(cookies)
    print(f"🎨 Quantos painters usar? (1-{max_painters})")
    
    try:
        num_painters = int(input(f"Número de painters [1-{max_painters}]: ") or "1")
        if not (1 <= num_painters <= max_painters):
            print(f"❌ Deve estar entre 1 e {max_painters}")
            return
    except ValueError:
        print("❌ Número inválido")
        return
    
    # Selecionar cookies a usar
    selected_cookies = cookies[:num_painters]
    
    try:
        # Coleta de dados
        image_path = input("\n📁 Caminho da imagem: ").strip()
        if not image_path:
            print("❌ Caminho da imagem é obrigatório")
            return
        
        # Verificar se arquivo existe
        if not os.path.exists(image_path):
            print(f"❌ Arquivo '{image_path}' não encontrado")
            return
        
        # Opção de localização
        print("\n🏙️ Onde você quer pintar?")
        print("   [1] Na sua cidade (Tile 708, 1164)")
        print("   [2] Em qualquer lugar (escolher coordenadas)")
        
        location_choice = input("\nEscolha (1 ou 2): ").strip()
        
        if location_choice == "1":
            # Pintar na cidade (coordenadas fixas)
            tl_x, tl_y = 708, 1164
            print(f"\n🏙️ Pintando na sua cidade: Tile ({tl_x}, {tl_y})")
            print("\n📍 Posição inicial dentro da sua cidade:")
            px_x = int(input("   Px X (pixel 0-999): "))
            px_y = int(input("   Px Y (pixel 0-999): "))
            
        elif location_choice == "2":
            # Pintar em qualquer lugar
            print("\n🗺️ Escolha as coordenadas:")
            tl_x = int(input("   Tl X (tile): "))
            tl_y = int(input("   Tl Y (tile): "))
            px_x = int(input("   Px X (pixel 0-999): "))
            px_y = int(input("   Px Y (pixel 0-999): "))
            
        else:
            print("❌ Opção inválida! Use 1 ou 2.")
            return
        
        # Validação das coordenadas de pixel
        if not (0 <= px_x <= 999 and 0 <= px_y <= 999):
            print("❌ Erro: Px X e Px Y devem estar entre 0 e 999")
            return
        
        output_json = input("\n💾 Arquivo JSON de saída (Enter para pular): ").strip() or None
        delay = float(input("⏱️ Delay entre pixels em segundos [1.0]: ") or "1.0")
        
        if delay < 0:
            print("❌ Delay deve ser não-negativo")
            return
        
        # Configuração de droplets
        print("\n💰 CONFIGURAÇÃO DE DROPLETS:")
        print("   [1] Monitoramento automático (recomendado)")
        print("   [2] Sem monitoramento")
        
        droplet_choice = input("\nEscolha (1 ou 2): ").strip()
        
        if droplet_choice == "1":
            target_droplets = int(input("Meta de droplets [500]: ") or "500")
            check_interval = int(input("Check a cada quantos segundos [30]: ") or "30")
            auto_droplets = True
        else:
            auto_droplets = False
            target_droplets = 500
            check_interval = 30
        
        print("\n" + "="*60)
        print("🔧 CONFIGURAÇÃO:")
        print(f"   📁 Imagem: {image_path}")
        print(f"   🎨 Painters: {num_painters}")
        if location_choice == "1":
            print(f"   🏙️ Local: Sua cidade - Tile ({tl_x},{tl_y})")
        else:
            print(f"   🗺️ Local: Tile customizado ({tl_x},{tl_y})")
        print(f"   📍 Início: Px({px_x},{px_y})")
        print(f"   ⏱️ Delay: {delay}s por painter")
        if auto_droplets:
            print(f"   💰 Droplets: Monitoramento automático (meta: {target_droplets})")
        else:
            print(f"   💰 Droplets: Sem monitoramento")
        print("="*60)
        
        # Confirma início
        confirm = input(f"\n🚀 Iniciar pintura com {num_painters} painters? (s/N): ").strip().lower()
        if confirm not in ['s', 'sim', 'y', 'yes']:
            print("❌ Operação cancelada")
            return
        
        # Inicializa sistema
        start_coord = WplaceCoordinate(tl_x, tl_y, px_x, px_y)
        coordinator = MultiPainterCoordinator(selected_cookies, delay)
        processor = WplaceImageProcessor(coordinator)
        
        # Inicia monitoramento de droplets se habilitado
        if auto_droplets:
            print(f"\n💰 Iniciando monitoramento de droplets...")
            # Inicia monitoramento em thread separada
            import threading
            droplet_thread = threading.Thread(
                target=lambda: coordinator.painters[0].droplet_manager.start_monitoring(
                    target_droplets, check_interval
                ),
                daemon=True
            )
            droplet_thread.start()
            print(f"✅ Monitoramento iniciado em background")
        
        # Executa pintura
        success = processor.paint_image(image_path, start_coord, output_json, resume=False)
        
        print("\n" + "="*60)
        if success:
            print("🎉 PROCESSO CONCLUÍDO COM SUCESSO!")
        else:
            print("❌ FALHA NO PROCESSO")
        print("="*60)
            
    except ValueError as e:
        print(f"❌ Erro de entrada: {str(e)}")
    except KeyboardInterrupt:
        print("\n\n⏹️ Processo interrompido pelo usuário")
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")

def resume_painting(cookie_manager: CookieManager, progress_manager: ProgressManager):
    """Continua pintura de onde parou."""
    if not progress_manager.has_backup():
        print("❌ Nenhum progresso salvo encontrado")
        return
    
    progress = progress_manager.load_progress()
    if not progress:
        print("❌ Erro ao carregar progresso")
        return
    
    print("\n📊 PROGRESSO SALVO ENCONTRADO:")
    print(f"   📁 Imagem: {progress['image_path']}")
    print(f"   📊 Progresso: {progress['completion_percentage']:.1f}%")
    print(f"   🕒 Salvo em: {progress['timestamp']}")
    print(f"   🎯 Pixels restantes: {progress['total_pixels'] - len(progress['completed_pixels'])}")
    
    cookies = cookie_manager.get_cookies()
    if not cookies:
        print("❌ Nenhum cookie salvo! Use o gerenciador de cookies primeiro.")
        return
    
    # Seleção de quantos cookies usar
    max_painters = len(cookies)
    print(f"\n🎨 Quantos painters usar? (1-{max_painters})")
    
    try:
        num_painters = int(input(f"Número de painters [1-{max_painters}]: ") or "1")
        if not (1 <= num_painters <= max_painters):
            print(f"❌ Deve estar entre 1 e {max_painters}")
            return
    except ValueError:
        print("❌ Número inválido")
        return
    
    selected_cookies = cookies[:num_painters]
    delay = float(input("⏱️ Delay entre pixels em segundos [1.0]: ") or "1.0")
    
    confirm = input(f"\n🚀 Continuar pintura com {num_painters} painters? (s/N): ").strip().lower()
    if confirm not in ['s', 'sim', 'y', 'yes']:
        print("❌ Operação cancelada")
        return
    
    try:
        # Inicializa sistema
        coordinator = MultiPainterCoordinator(selected_cookies, delay)
        processor = WplaceImageProcessor(coordinator)
        
        # Executa continuação da pintura
        success = processor.paint_image("", WplaceCoordinate(0, 0, 0, 0), None, resume=True)
        
        print("\n" + "="*60)
        if success:
            print("🎉 PINTURA CONTINUADA COM SUCESSO!")
        else:
            print("❌ FALHA NA CONTINUAÇÃO")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")

def check_saved_progress(progress_manager: ProgressManager):
    """Verifica progresso salvo."""
    if not progress_manager.has_backup():
        print("📋 Nenhum progresso salvo encontrado")
        return
    
    progress = progress_manager.load_progress()
    if not progress:
        print("❌ Erro ao carregar progresso")
        return
    
    print("\n📊 PROGRESSO SALVO:")
    print("="*50)
    print(f"📁 Imagem: {progress['image_path']}")
    print(f"📊 Progresso: {progress['completion_percentage']:.1f}%")
    print(f"🎯 Pixels pintados: {len(progress['completed_pixels'])}")
    print(f"🎯 Pixels totais: {progress['total_pixels']}")
    print(f"🎯 Pixels restantes: {progress['total_pixels'] - len(progress['completed_pixels'])}")
    print(f"🕒 Salvo em: {progress['timestamp']}")
    
    # Mostrar coordenada inicial
    coord = progress['start_coordinate']
    print(f"📍 Coordenada inicial: Tl({coord['tl_x']},{coord['tl_y']}) Px({coord['px_x']},{coord['px_y']})")
    
    print("="*50)
    
    # Opções
    print("\nOpções:")
    print("1. Continuar desta pintura")
    print("2. Remover progresso salvo")
    print("3. Voltar")
    
    choice = input("\nEscolha (1-3): ").strip()
    
    if choice == "2":
        confirm = input("🗑️ Tem certeza que deseja remover o progresso salvo? (s/N): ").strip().lower()
        if confirm in ['s', 'sim', 'y', 'yes']:
            progress_manager.clear_backup()
            print("✅ Progresso removido")

if __name__ == "__main__":
    main()