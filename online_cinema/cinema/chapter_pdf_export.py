from django.http import HttpResponse
from reportlab.pdfgen import canvas
from .models import Chapter, Episode
from django.contrib import admin
from io import BytesIO

from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

def export_chapter_pdf(modeladmin, request, queryset):
    if queryset.count() != 1:
        modeladmin.message_user(request, "Пожалуйста, выберите одну главу для экспорта.", level='error')
        return


    chapter = queryset.first()
    buffer = BytesIO()
    p = canvas.Canvas(buffer)

    
    pdfmetrics.registerFont(TTFont('Arial', 'C:/WINDOWS/FONTS/ARIAL.TTF'))  # Укажи правильный путь к шрифту
    p.setFont('Arial', 12)

    # Заголовок
    p.setFont("Arial", 16)
    p.drawString(100, 800, f"Информация о главе: {chapter.title}")

    y = 770
    p.setFont("Arial", 12)

    p.drawString(100, y, f"Дата релиза: {chapter.release_date}")
    y -= 20
    p.drawString(100, y, f"Рейтинг: {chapter.rating_cache}")
    y -= 20
    p.drawString(100, y, f"Просмотры: {chapter.view_count}")
    y -= 40

    # Обзор франшизы
    if chapter.franchise:
        p.setFont("Arial", 14)
        p.drawString(100, y, f"Обзор франшизы:")
        y -= 20
        p.setFont("Arial", 12)
        overview = chapter.franchise.get_chapter_overview()
        for line in overview:
            p.drawString(110, y, f"- {line}")
            y -= 15

    y -= 30
    p.setFont("Arial", 14)
    p.drawString(100, y, "Эпизоды:")
    y -= 20

    episodes = chapter.episodes.all()
    p.setFont("Arial", 12)
    for episode in episodes:
        if y < 50:  # Создаем новую страницу при необходимости
            p.showPage()
            y = 800
        p.drawString(110, y, f"{episode.episode_number}. {episode.title} — {episode.duration} мин.")
        y -= 15

    p.showPage()
    p.save()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=chapter_{chapter.id}.pdf'
    return response


export_chapter_pdf.short_description = "Скачать информацию о главе в PDF"
