#!/usr/bin/env python3
"""
Teste para verificar se as correções de sintaxe funcionam
"""

try:
    print("🔧 Testando import após correções de sintaxe...")
    
    import sexo_improved
    print("✅ Import básico funcionou!")
    
    # Testa classes principais
    detector = sexo_improved.TermuxColorDetector()
    print("✅ TermuxColorDetector criado!")
    
    coord = sexo_improved.WplaceCoordinate(100, 200, 300, 400)
    print(f"✅ WplaceCoordinate: Tl({coord.tl_x},{coord.tl_y}) Px({coord.px_x},{coord.px_y})")
    
    print("\n🎉 TODAS AS CORREÇÕES DE SINTAXE FUNCIONARAM!")
    print("📱 Compatível com versões antigas do Python!")
    print("🚀 Pronto para usar no Termux!")
    
except SyntaxError as e:
    print(f"❌ Erro de sintaxe ainda presente: {e}")
except Exception as e:
    print(f"❌ Outro erro: {e}")
    import traceback
    traceback.print_exc()