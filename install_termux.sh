#!/bin/bash

echo "📱 INSTALAÇÃO DO WPLACE PAINTER PARA TERMUX"
echo "=" * 50

# Atualizar sistema
echo "🔄 Atualizando sistema..."
pkg update -y
pkg upgrade -y

# Instalar Python e dependências básicas
echo "🐍 Instalando Python..."
pkg install python -y

# Instalar git
echo "📦 Instalando Git..."
pkg install git -y

# Instalar bibliotecas Python compatíveis com Termux
echo "📚 Instalando bibliotecas Python..."
pip install --break-system-packages Pillow requests colorthief

# Verificar instalação
echo "✅ Verificando instalação..."
python3 -c "import PIL, requests, colorthief; print('✅ Todas as bibliotecas instaladas com sucesso!')"

echo ""
echo "🎉 INSTALAÇÃO CONCLUÍDA!"
echo "📱 Sistema pronto para uso no Termux!"
echo ""
echo "🚀 Para usar:"
echo "   python3 sexo_improved.py"
echo ""
echo "📊 Para monitorar logs:"
echo "   tail -f wplace_painter.log"