import os
from django.http import HttpResponse, Http404
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Chapter, Episode

User = get_user_model()


class VideoStreamView(APIView):
    """
    Стриминг видеофайлов с поддержкой HTTP Range requests.
    GET /api/v1/video/chapters/{chapter_id}/
    GET /api/v1/video/episodes/{episode_id}/
    """
    permission_classes = [AllowAny]  # Можно изменить на IsAuthenticated для платного контента

    def get(self, request, chapter_id=None, episode_id=None, *args, **kwargs):
        # Определяем, что стримим: главу или эпизод
        if chapter_id:
            content = Chapter.objects.filter(id=chapter_id).first()
            if not content:
                raise Http404("Глава не найдена")
            # Для глав используем трейлер или первое видео
            video_field = getattr(content, 'trailer_video', None) or getattr(content, 'video_file', None)
        elif episode_id:
            content = Episode.objects.filter(id=episode_id).first()
            if not content:
                raise Http404("Эпизод не найдена")
            video_field = getattr(content, 'video_file', None)
        else:
            raise Http404("Не указан контент")

        if not video_field:
            return Response({'detail': 'Видеофайл не найден'}, status=404)

        video_path = video_field.path if hasattr(video_field, 'path') else str(video_field)
        
        # Проверка существования файла
        if not os.path.exists(video_path):
            return Response({'detail': 'Файл не найден на сервере'}, status=404)

        # Проверка прав доступа (опционально)
        if content.required_subscription and not request.user.is_authenticated:
            # Проверяем подписку
            has_access = self._check_subscription_access(request.user, content.required_subscription)
            if not has_access:
                return Response({'detail': 'Требуется подписка для просмотра'}, status=403)

        return self._stream_video(request, video_path)

    def _check_subscription_access(self, user, subscription):
        """Проверяет, есть ли у пользователя доступ к подписке"""
        if not user or not user.is_authenticated:
            return False
        return user.subscriptions.filter(
            subscription=subscription,
            is_active=True,
            end_date__gte=timezone.now()
        ).exists()

    def _stream_video(self, request, file_path):
        """
        Стримит видеофайл с поддержкой HTTP Range requests.
        Позволяет перемотку и буферизацию.
        """
        file_size = os.path.getsize(file_path)
        range_header = request.META.get('HTTP_RANGE', '').strip()
        
        # Если нет Range header — отдаём весь файл
        if not range_header:
            with open(file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='video/mp4')
                response['Content-Length'] = file_size
                response['Accept-Ranges'] = 'bytes'
                return response

        # Парсим Range header
        try:
            unit, range_value = range_header.split('=')
            if unit != 'bytes':
                raise ValueError
            start_str, end_str = range_value.split('-', 1)
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
        except (ValueError, IndexError):
            # Если не удалось распарсить — отдаём с начала
            start, end = 0, file_size - 1

        # Валидация диапазона
        if start >= file_size:
            start = file_size - 1
        if end >= file_size:
            end = file_size - 1
        if start > end:
            start, end = 0, file_size - 1

        content_length = end - start + 1

        with open(file_path, 'rb') as f:
            f.seek(start)
            chunk = f.read(content_length)

        response = HttpResponse(chunk, content_type='video/mp4', status=206)
        response['Content-Length'] = content_length
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Accept-Ranges'] = 'bytes'
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate'
        
        return response