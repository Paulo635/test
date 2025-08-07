#!/usr/bin/env python3
"""
Sistema de detecção de cores compatível com Termux
Usa PIL + colorthief ao invés de OpenCV
"""

import json
import time
import math
import logging
from PIL import Image, ImageStat
from colorthief import ColorThief
from typing import Tuple, Optional, Dict, List
import colorsys

logger = logging.getLogger(__name__)

class TermuxColorDetector:
    """Sistema de detecção de cores otimizado para Termux."""
    
    def __init__(self):
        self.color_cache = {}
        self.palette_cache = {}
    
    def rgb_to_hsv(self, rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """Converte RGB para HSV."""
        r, g, b = rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0
        return colorsys.rgb_to_hsv(r, g, b)
    
    def hsv_to_rgb(self, hsv: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """Converte HSV para RGB."""
        rgb = colorsys.hsv_to_rgb(hsv[0], hsv[1], hsv[2])
        return (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
    
    def get_dominant_colors_pil(self, image_path: str, n_colors: int = 8) -> List[Tuple[int, int, int]]:
        """Extrai cores dominantes usando PIL (mais compatível com Termux)."""
        try:
            img = Image.open(image_path).convert("RGB")
            
            # Redimensiona para processamento mais rápido
            width, height = img.size
            if width * height > 1000000:  # Se imagem muito grande
                scale = math.sqrt(1000000 / (width * height))
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Converte para lista de pixels
            pixels = list(img.getdata())
            
            # Agrupa pixels similares
            color_groups = {}
            for pixel in pixels:
                # Arredonda para reduzir variações
                rounded = tuple(c // 10 * 10 for c in pixel)
                if rounded in color_groups:
                    color_groups[rounded] += 1
                else:
                    color_groups[rounded] = 1
            
            # Ordena por frequência
            sorted_colors = sorted(color_groups.items(), key=lambda x: x[1], reverse=True)
            
            # Retorna as cores mais frequentes
            return [color for color, count in sorted_colors[:n_colors]]
            
        except Exception as e:
            logger.error(f"Erro no PIL color detection: {e}")
            return []
    
    def get_dominant_colors_colorthief(self, image_path: str, n_colors: int = 8) -> List[Tuple[int, int, int]]:
        """Extrai cores dominantes usando ColorThief."""
        try:
            color_thief = ColorThief(image_path)
            palette = color_thief.get_palette(color_count=n_colors, quality=10)
            return palette
        except Exception as e:
            logger.error(f"Erro no ColorThief: {e}")
            return []
    
    def get_average_color_region_pil(self, image_path: str, x: int, y: int, size: int = 5) -> Tuple[int, int, int]:
        """Obtém cor média de uma região usando PIL."""
        try:
            img = Image.open(image_path).convert("RGB")
            width, height = img.size
            
            # Define região
            x1 = max(0, x - size//2)
            y1 = max(0, y - size//2)
            x2 = min(width, x + size//2)
            y2 = min(height, y + size//2)
            
            # Extrai região
            region = img.crop((x1, y1, x2, y2))
            
            # Calcula cor média
            stat = ImageStat.Stat(region)
            avg_color = tuple(int(c) for c in stat.mean)
            
            return avg_color
            
        except Exception as e:
            logger.error(f"Erro ao obter cor média: {e}")
            return (0, 0, 0)
    
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
    
    def analyze_image_colors_termux(self, image_path: str) -> Dict[str, List[Tuple[int, int, int]]]:
        """Análise completa de cores da imagem usando bibliotecas compatíveis com Termux."""
        result = {
            'pil_colors': self.get_dominant_colors_pil(image_path),
            'colorthief_colors': self.get_dominant_colors_colorthief(image_path),
            'average_colors': []
        }
        
        # Calcula cores médias de diferentes regiões
        try:
            img = Image.open(image_path).convert("RGB")
            width, height = img.size
            
            # Amostra cores de diferentes regiões
            regions = [
                (width//4, height//4),
                (width//2, height//2),
                (3*width//4, 3*height//4),
                (width//4, 3*height//4),
                (3*width//4, height//4)
            ]
            
            for x, y in regions:
                avg_color = self.get_average_color_region_pil(image_path, x, y, 20)
                result['average_colors'].append(avg_color)
                
        except Exception as e:
            logger.error(f"Erro na análise de cores: {e}")
        
        return result
    
    def get_optimal_color_mapping_termux(self, image_path: str, 
                                       wplace_palette: Dict[Tuple[int, int, int], int]) -> Dict[Tuple[int, int, int], int]:
        """Cria mapeamento otimizado de cores para o Wplace usando bibliotecas compatíveis com Termux."""
        
        # Analisa cores da imagem
        color_analysis = self.analyze_image_colors_termux(image_path)
        
        # Combina todos os métodos para melhor precisão
        all_colors = set()
        all_colors.update(color_analysis['pil_colors'])
        all_colors.update(color_analysis['colorthief_colors'])
        all_colors.update(color_analysis['average_colors'])
        
        # Cria mapeamento otimizado
        optimal_mapping = {}
        
        for color in all_colors:
            if color not in optimal_mapping:
                best_match = self.find_best_color_match(color, wplace_palette)
                optimal_mapping[color] = best_match
        
        logger.info(f"Mapeamento otimizado criado com {len(optimal_mapping)} cores (Termux compatível)")
        return optimal_mapping

# Paleta do Wplace.live
WPLACE_PALETTE = {
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

def test_termux_color_detection():
    """Testa o sistema de detecção de cores compatível com Termux."""
    print("🧪 TESTE DE DETECÇÃO DE CORES (TERMUX COMPATÍVEL)")
    print("=" * 60)
    
    detector = TermuxColorDetector()
    
    # Testa com cores conhecidas
    test_colors = [
        ((255, 0, 0), "Vermelho puro"),
        ((0, 255, 0), "Verde puro"),
        ((0, 0, 255), "Azul puro"),
        ((255, 255, 0), "Amarelo"),
        ((128, 128, 128), "Cinza médio"),
    ]
    
    print("🔍 Testando correspondência de cores...")
    
    for target_rgb, color_name in test_colors:
        print(f"\n🎨 Testando: {color_name} {target_rgb}")
        
        best_match = detector.find_best_color_match(target_rgb, WPLACE_PALETTE)
        matched_color = list(WPLACE_PALETTE.keys())[best_match]
        
        print(f"   ✅ Melhor correspondência: {matched_color} (índice {best_match})")
        
        # Calcula distância
        distance = sum((a - b) ** 2 for a, b in zip(target_rgb, matched_color))
        print(f"   📊 Distância: {distance:.1f}")
    
    print("\n✅ Teste concluído!")
    print("📱 Sistema totalmente compatível com Termux!")

if __name__ == "__main__":
    test_termux_color_detection()