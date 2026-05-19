# cinema/subscription_pdf_export.py
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib import messages
import weasyprint
from .models import UserSubscription


def export_subscription_pdf(modeladmin, request, queryset):
    """
    Django admin action: генерация PDF-квитанций для выбранных подписок.
    Если выбрана одна подписка — файл скачивается сразу.
    Если несколько — показывается сообщение с инструкцией (или можно реализовать архив).
    """
    
    # Если выбрана ровно одна подписка — генерируем и отдаём файл
    if queryset.count() == 1:
        subscription = queryset.first()
        
        html = render_to_string('cinema/pdf/subscription_receipt.html', {
            'subscription': subscription,
            'user': subscription.user,
        })
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'filename=subscription_{subscription.id}_receipt.pdf'
        
        try:
            weasyprint.HTML(string=html).write_pdf(response)
            messages.success(request, f'✅ Квитанция для подписки #{subscription.id} сгенерирована.')
            return response
        except Exception as e:
            messages.error(request, f'❌ Ошибка генерации PDF: {str(e)}')
            return None
    
    # Если выбрано несколько — информируем пользователя (расширение: можно сделать ZIP-архив)
    else:
        messages.info(
            request, 
            f'📄 Выбрано {queryset.count()} подписок. Генерация нескольких PDF одновременно не поддерживается. '
            f'Пожалуйста, выберите одну подписку для скачивания квитанции.'
        )
        return None


export_subscription_pdf.short_description = "📄 Скачать квитанцию (PDF)"