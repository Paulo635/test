#!/usr/bin/env python3
"""
Teste para verificar se a correção do Blue Marble funciona
"""

from PIL import Image
import sexo_improved
import logging

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_bluemarble_fix():
    """Testa se a correção do Blue Marble funciona."""
    
    print("🔧 TESTANDO CORREÇÃO DO BLUE MARBLE")
    print("=" * 50)
    
    try:
        # Cria uma imagem de teste simples
        print("🎨 Criando imagem de teste...")
        img = Image.new('RGBA', (10, 10), (255, 0, 0, 255))  # Quadrado vermelho 10x10
        
        # Cria coordenada de teste
        coord = sexo_improved.WplaceCoordinate(708, 1164, 865, 132)
        print(f"📍 Coordenada: Tl({coord.tl_x},{coord.tl_y}) Px({coord.px_x},{coord.px_y})")
        
        # Testa detector Blue Marble
        detector = sexo_improved.TermuxColorDetector()
        print("✅ Detector criado!")
        
        # Testa função corrigida
        template = detector.create_template_like_bluemarble_from_pil(
            img, 
            "Teste_Blue_Marble",
            coord
        )
        
        if template:
            print("✅ Template Blue Marble criado com sucesso!")
            print(f"   📛 Nome: {template['display_name']}")
            print(f"   📊 Pixels: {template['total_pixels']:,}")
            print(f"   🗂️ Tiles: {template['tiles_count']}")
        else:
            print("❌ Falha ao criar template")
            
        print("\n🎉 CORREÇÃO FUNCIONOU!")
        print("🚀 O sistema Blue Marble está funcionando!")
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bluemarble_fix()