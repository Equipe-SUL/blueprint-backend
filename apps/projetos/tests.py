import os
from django.test import SimpleTestCase
from apps.projetos.ai.vision import analisar_imagem_com_vlm


class VLMTests(SimpleTestCase):
    """Testes para a função de análise VLM (Visão Computacional - Alvenaria)"""

    def test_analisar_imagem_alvenaria(self):
        """Testa a análise de uma imagem de planta de alvenaria"""
        from django.conf import settings

        # Permite override via variável de ambiente para teste local
        caminho_rel = os.getenv("VLM_TEST_IMAGE", "test_fixtures/planta_alvenaria_teste.jpg")

        # Se for caminho relativo, converte para absoluto baseado no ROOT_DIR
        if not os.path.isabs(caminho_rel):
            caminho_imagem = os.path.join(settings.BASE_DIR, caminho_rel)
        else:
            caminho_imagem = caminho_rel

        if not os.path.exists(caminho_imagem):
            self.skipTest(f"Imagem de teste não encontrada: {caminho_imagem}")

        resultado = analisar_imagem_com_vlm(caminho_imagem=caminho_imagem)

        # Verifica se a função retornou uma estrutura válida
        self.assertIn("sucesso", resultado)
        self.assertIn("dados", resultado)
        self.assertIn("disciplina_aplicada", resultado)
        self.assertIn("erro", resultado)

        # Verifica se a disciplina está correta
        self.assertEqual(resultado["disciplina_aplicada"], "alvenaria")

        # Se sucesso, verifica se os dados são um dicionário
        if resultado["sucesso"]:
            self.assertIsInstance(resultado["dados"], dict)
            print(f"\nVLM funcionou! Dados: {resultado['dados']}")
        else:
            print(f"\nVLM falhou: {resultado['erro']}")
