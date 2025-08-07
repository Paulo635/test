#!/usr/bin/env python3
"""
Teste para verificar se o import do sexo_improved.py funciona
"""

try:
    print("🔄 Testando import do sexo_improved.py...")
    
    # Testa import básico
    import sexo_improved
    print("✅ Import básico funcionou!")
    
    # Testa classes principais
    detector = sexo_improved.TermuxColorDetector()
    print("✅ TermuxColorDetector criado!")
    
    coord = sexo_improved.WplaceCoordinate(100, 200, 300, 400)
    print(f"✅ WplaceCoordinate criado: Tl({coord.tl_x},{coord.tl_y}) Px({coord.px_x},{coord.px_y})")
    
    print("\n🎉 TODOS OS IMPORTS FUNCIONARAM!")
    print("📱 O código está pronto para usar no Termux!")
    
except Exception as e:
    print(f"❌ Erro no import: {e}")
    import traceback
    traceback.print_exc()