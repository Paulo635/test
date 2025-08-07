#!/usr/bin/env python3
"""
Melhorias na distribuição de trabalho entre painters
- Distribuição mais inteligente
- Monitoramento individual por painter
- Sistema de droplets integrado
"""

import logging
import time
import threading
from typing import List, Tuple, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PainterStats:
    """Estatísticas de cada painter."""
    painter_id: int
    pixels_painted: int
    successful_paints: int
    failed_paints: int
    droplets_used: int
    last_activity: float

class ImprovedWorkDistributor:
    """Distribuidor de trabalho melhorado com monitoramento individual."""
    
    def __init__(self, num_painters: int):
        self.num_painters = num_painters
        self.painter_stats = {}
        self.distribution_lock = threading.Lock()
        
        # Inicializa estatísticas para cada painter
        for i in range(num_painters):
            self.painter_stats[i] = PainterStats(
                painter_id=i+1,
                pixels_painted=0,
                successful_paints=0,
                failed_paints=0,
                droplets_used=0,
                last_activity=time.time()
            )
    
    def distribute_work_intelligent(self, paint_sequence: List[Tuple], 
                                  painter_capacities: Dict[int, float] = None) -> List[List]:
        """Distribui trabalho de forma inteligente baseada na capacidade de cada painter."""
        
        if not paint_sequence:
            return [[] for _ in range(self.num_painters)]
        
        # Se não especificado, assume capacidade igual para todos
        if painter_capacities is None:
            painter_capacities = {i: 1.0 for i in range(self.num_painters)}
        
        # Calcula pesos baseados na capacidade
        total_capacity = sum(painter_capacities.values())
        painter_weights = {i: cap/total_capacity for i, cap in painter_capacities.items()}
        
        # Distribui trabalho proporcionalmente
        chunks = []
        current_pos = 0
        
        for painter_id in range(self.num_painters):
            weight = painter_weights[painter_id]
            chunk_size = int(len(paint_sequence) * weight)
            
            # Garante que o último painter pega o resto
            if painter_id == self.num_painters - 1:
                chunk_size = len(paint_sequence) - current_pos
            
            chunk = paint_sequence[current_pos:current_pos + chunk_size]
            chunks.append(chunk)
            current_pos += chunk_size
            
            logger.info(f"Painter {painter_id+1}: {len(chunk)} pixels (peso: {weight:.2f})")
        
        return chunks
    
    def update_painter_stats(self, painter_id: int, success: bool, droplets_used: int = 0):
        """Atualiza estatísticas de um painter."""
        with self.distribution_lock:
            if painter_id in self.painter_stats:
                stats = self.painter_stats[painter_id]
                stats.pixels_painted += 1
                stats.last_activity = time.time()
                
                if success:
                    stats.successful_paints += 1
                else:
                    stats.failed_paints += 1
                
                stats.droplets_used += droplets_used
    
    def get_painter_performance(self, painter_id: int) -> Dict:
        """Obtém performance de um painter específico."""
        if painter_id in self.painter_stats:
            stats = self.painter_stats[painter_id]
            success_rate = (stats.successful_paints / stats.pixels_painted * 100) if stats.pixels_painted > 0 else 0
            
            return {
                'painter_id': stats.painter_id,
                'pixels_painted': stats.pixels_painted,
                'successful_paints': stats.successful_paints,
                'failed_paints': stats.failed_paints,
                'success_rate': success_rate,
                'droplets_used': stats.droplets_used,
                'last_activity': stats.last_activity
            }
        return {}
    
    def get_all_performance(self) -> List[Dict]:
        """Obtém performance de todos os painters."""
        return [self.get_painter_performance(i) for i in range(self.num_painters)]
    
    def print_performance_summary(self):
        """Imprime resumo de performance de todos os painters."""
        print("\n📊 RESUMO DE PERFORMANCE DOS PAINTERS:")
        print("=" * 60)
        
        total_painted = 0
        total_successful = 0
        
        for i in range(self.num_painters):
            perf = self.get_painter_performance(i)
            if perf:
                print(f"🎨 Painter {perf['painter_id']}:")
                print(f"   📊 Pixels pintados: {perf['pixels_painted']}")
                print(f"   ✅ Sucessos: {perf['successful_paints']}")
                print(f"   ❌ Falhas: {perf['failed_paints']}")
                print(f"   📈 Taxa de sucesso: {perf['success_rate']:.1f}%")
                print(f"   💧 Droplets usados: {perf['droplets_used']}")
                
                total_painted += perf['pixels_painted']
                total_successful += perf['successful_paints']
        
        if total_painted > 0:
            overall_success_rate = (total_successful / total_painted) * 100
            print(f"\n🎯 TOTAL:")
            print(f"   📊 Pixels pintados: {total_painted}")
            print(f"   ✅ Sucessos: {total_successful}")
            print(f"   📈 Taxa de sucesso geral: {overall_success_rate:.1f}%")

class DropletAwarePainter:
    """Painter com consciência de droplets."""
    
    def __init__(self, cookie: str, painter_id: int, delay: float = 1.0):
        self.cookie = cookie
        self.painter_id = painter_id
        self.delay = delay
        self.droplet_manager = None  # Será inicializado depois
        
        # Estatísticas
        self.pixels_painted = 0
        self.successful_paints = 0
        self.failed_paints = 0
        self.droplets_used = 0
        
        # Headers da sessão
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
            'Accept-Encoding': "gzip, deflate, br, zstd",
            'Content-Type': "text/plain;charset=UTF-8",
            'sec-ch-ua-platform': '"Android"',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
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
    
    def set_droplet_manager(self, droplet_manager):
        """Define o gerenciador de droplets."""
        self.droplet_manager = droplet_manager
    
    def paint_pixel_with_droplets(self, coord, color_index, stats_updater=None):
        """Pinta pixel com monitoramento de droplets."""
        success = self.paint_pixel(coord, color_index)
        
        # Atualiza estatísticas
        self.pixels_painted += 1
        if success:
            self.successful_paints += 1
            self.droplets_used += 1
        else:
            self.failed_paints += 1
        
        # Atualiza estatísticas globais se fornecido
        if stats_updater:
            stats_updater(self.painter_id, success, 1 if success else 0)
        
        return success
    
    def paint_pixel(self, coord, color_index):
        """Pinta um pixel (implementação básica - será sobrescrita)."""
        # Esta é uma implementação placeholder
        # A implementação real está no arquivo principal
        pass

def test_improved_distribution():
    """Testa a distribuição melhorada."""
    print("🧪 TESTE DA DISTRIBUIÇÃO MELHORADA")
    print("=" * 50)
    
    # Simula sequência de pintura
    paint_sequence = [(f"coord_{i}", f"color_{i}") for i in range(1000)]
    
    # Testa distribuição com diferentes capacidades
    distributor = ImprovedWorkDistributor(4)
    
    print("📊 Distribuição com capacidades iguais:")
    chunks_equal = distributor.distribute_work_intelligent(paint_sequence)
    
    for i, chunk in enumerate(chunks_equal):
        print(f"   Painter {i+1}: {len(chunk)} pixels")
    
    print("\n📊 Distribuição com capacidades diferentes:")
    capacities = {0: 0.5, 1: 0.3, 2: 0.15, 3: 0.05}  # Painter 1 mais forte
    chunks_weighted = distributor.distribute_work_intelligent(paint_sequence, capacities)
    
    for i, chunk in enumerate(chunks_weighted):
        print(f"   Painter {i+1}: {len(chunk)} pixels")
    
    # Simula algumas pinturas
    for painter_id in range(4):
        for _ in range(10):
            success = (painter_id % 2 == 0)  # Simula sucesso alternado
            distributor.update_painter_stats(painter_id, success, 1)
    
    # Mostra performance
    distributor.print_performance_summary()

if __name__ == "__main__":
    test_improved_distribution()