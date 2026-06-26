import random
from django.core.management.base import BaseCommand
from django.db import transaction
from cinema.models import Chapter, Review, Rating, User

class Command(BaseCommand):
    help = 'Создает по 10 случайных отзывов и оценок для каждой главы (фильма/сериала)'

    # Безопасные фразы, не содержащие запрещённых слов из Review.clean()
    SAFE_REVIEW_TEXTS = [
        "Отличный фильм, очень понравился!",
        "Сюжет закручен хорошо, рекомендую к просмотру.",
        "Неплохо, но концовка немного скомкана.",
        "Актерская игра на высшем уровне.",
        "Визуальные эффекты просто потрясающие.",
        "Ожидал большего, но в целом нормально.",
        "Идеально для вечернего просмотра с семьей.",
        "Классика жанра, стоит пересмотреть.",
        "Немного затянуто, но атмосфера компенсирует.",
        "Звук и музыка подобраны идеально.",
        "Режиссёрский стиль узнаваем и цепляет.",
        "Финал заставил задуматься над смыслом.",
        "Отличная экранизация, близко к первоисточнику.",
        "Динамично, ярко и без лишней воды.",
        "Герои раскрыты глубоко, сопереживаешь каждому."
    ]

    def handle(self, *args, **options):
        self.stdout.write('🔄 Загрузка данных из БД...')
        
        chapters = list(Chapter.objects.all())
        if not chapters:
            self.stdout.write(self.style.ERROR('❌ В базе нет ни одной главы. Добавьте контент перед запуском.'))
            return

        users = list(User.objects.all())
        # Гарантируем минимум 10 уникальных пользователей для соблюдения unique_together
        if len(users) < 10:
            self.stdout.write(self.style.WARNING(f'⚠️ Найдено только {len(users)} пользователей. Создаю временных...'))
            for _ in range(10 - len(users)):
                username = f"test_user_{random.randint(10000, 99999)}"
                User.objects.create_user(
                    username=username,
                    email=f"{username}@example.com",
                    password="SecurePass123!"
                )
            users = list(User.objects.all())
            self.stdout.write(self.style.SUCCESS(f'✅ Создано тестовых пользователей. Всего: {len(users)}'))

        self.stdout.write(f'📊 Найдено глав: {len(chapters)}, пользователей: {len(users)}')
        total_created = 0

        for chapter in chapters:
            self.stdout.write(f'📝 Обработка: {chapter.title or f"Глава #{chapter.id}"}')
            
            # Исключаем пользователей, уже оставивших отзыв на эту главу
            existing_user_ids = set(Review.objects.filter(chapter=chapter).values_list('user_id', flat=True))
            available_users = [u for u in users if u.id not in existing_user_ids][:10]

            if not available_users:
                self.stdout.write('   ⚠️ Все пользователи уже оставили отзыв. Пропуск.')
                continue

            for user in available_users:
                try:
                    with transaction.atomic():
                        # 1. Создаём отзыв
                        Review.objects.create(
                            user=user,
                            chapter=chapter,
                            text=random.choice(self.SAFE_REVIEW_TEXTS),
                            likes_count=random.randint(0, 120),
                            dislikes_count=random.randint(0, 15)
                        )
                        # 2. Создаём оценку (score 1-10)
                        Rating.objects.create(
                            user=user,
                            chapter=chapter,
                            score=random.randint(1, 10)
                        )
                        total_created += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   ❌ Ошибка для {user.username}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\n✅ Готово! Успешно создано {total_created} пар (отзыв + оценка).'))
        self.stdout.write(self.style.WARNING('💡 Не забудьте пересчитать rating_cache в Chapter, если используете его в продакшене.'))