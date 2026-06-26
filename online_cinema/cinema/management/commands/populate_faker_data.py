import random
import datetime
from decimal import Decimal

from django.db import transaction
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker

from cinema.models import (
    User, UserPaymentMethod, Subscription, UserSubscription,
    Comment, Review, Rating, Playlist, PlaylistChapter, ViewHistory,
    Chapter
)

fake = Faker(['ru_RU', 'en_US'])
Faker.seed(42)


class Command(BaseCommand):
    help = 'Наполняет БД тестовыми данными (исправлены таймзоны и UNIQUE-конфликты плейлистов)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('🎭 Начинаем генерацию тестовых данных...'))

        with transaction.atomic():
            self.stdout.write('👥 Создаём пользователей...')
            users = [self._generate_fake_user() for _ in range(15)]
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано/обновлено: {len(users)} пользователей'))

            self.stdout.write('💳 Создаём типы подписок...')
            subscriptions = self._create_subscriptions()
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано: {len(subscriptions)} типов подписок'))

            self.stdout.write('💰 Создаём платёжные методы и подписки...')
            user_subs_created = 0
            for user in users:
                payment_methods = self._create_payment_methods(user)
                if fake.boolean(chance_of_getting_true=60):
                    sub_type = random.choice(list(subscriptions.values()))
                    self._create_user_subscription(user, sub_type, payment_methods)
                    user_subs_created += 1
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано: {user_subs_created} пользовательских подписок'))

            chapters = list(Chapter.objects.all())
            if not chapters:
                self.stderr.write(self.style.ERROR("⚠️ В базе нет глав (Chapter). Запустите сначала скрипты с кино-контентом!"))
                return
            self.stdout.write(f'🎬 Найдено глав: {len(chapters)}')

            self.stdout.write('💬 Создаём комментарии...')
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано: {self._create_comments(users, chapters)} комментариев'))

            self.stdout.write('⭐ Создаём отзывы...')
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано: {self._create_reviews(users, chapters)} отзывов'))

            self.stdout.write('🔢 Создаём оценки...')
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано: {self._create_ratings(users, chapters)} оценок'))

            self.stdout.write('📋 Создаём плейлисты...')
            playlists = self._create_playlists(users)
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано: {len(playlists)} плейлистов'))

            self.stdout.write('🔗 Добавляем главы в плейлисты...')
            self.stdout.write(self.style.SUCCESS(f'   ✓ Добавлено: {self._create_playlist_chapters(playlists, chapters)} записей'))

            self.stdout.write('👁️ Создаём историю просмотров...')
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано: {self._create_view_history(users, chapters)} записей'))

            self.stdout.write('\n' + '='*50)
            self.stdout.write(self.style.SUCCESS('✅ ГОТОВО! Статистика:'))
            self.stdout.write('='*50)
            self.stdout.write(f"👥 Пользователи:          {User.objects.count()}")
            self.stdout.write(f"💳 Способы оплаты:        {UserPaymentMethod.objects.count()}")
            self.stdout.write(f"📦 Типы подписок:         {Subscription.objects.count()}")
            self.stdout.write(f"🔁 Подписки пользователей: {UserSubscription.objects.count()}")
            self.stdout.write(f"💬 Комментарии:           {Comment.objects.count()}")
            self.stdout.write(f"⭐ Отзывы:                {Review.objects.count()}")
            self.stdout.write(f"🔢 Оценки:                {Rating.objects.count()}")
            self.stdout.write(f"📋 Плейлисты:             {Playlist.objects.count()}")
            self.stdout.write(f"🔗 Главы в плейлистах:    {PlaylistChapter.objects.count()}")
            self.stdout.write(f"👁️ История просмотров:    {ViewHistory.objects.count()}")
            self.stdout.write('='*50)

    # ================= ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =================

    def _make_aware(self, dt):
        if dt and timezone.is_naive(dt):
            return timezone.make_aware(dt)
        return dt

    def _generate_fake_user(self):
        username = fake.user_name()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': fake.email(), 'first_name': fake.first_name(), 'last_name': fake.last_name(),
                'description': fake.paragraph(nb_sentences=3), 'login_code': fake.uuid4()[:12],
                'date_joined': self._make_aware(fake.date_time_between(start_date='-2y', end_date='now')),
                'is_active': fake.boolean(chance_of_getting_true=90),
            }
        )
        if created:
            user.set_password(fake.password(length=12))
            user.save(update_fields=['password'])
        return user

    def _create_subscriptions(self):
        plans = [
            {"title": "Базовый", "price": 4.99, "days": 30, "desc": "Доступ к базовой библиотеке."},
            {"title": "Стандарт", "price": 9.99, "days": 30, "desc": "Full HD, 2 устройства."},
            {"title": "Премиум", "price": 14.99, "days": 30, "desc": "4K HDR, все устройства."},
            {"title": "Годовой Стандарт", "price": 99.99, "days": 365, "desc": "Годовая подписка со скидкой."},
            {"title": "Семейный", "price": 19.99, "days": 30, "desc": "До 6 профилей."},
        ]
        subs = {}
        for p in plans:
            s, _ = Subscription.objects.get_or_create(
                title=p["title"],
                defaults={'price_usd': Decimal(str(p["price"])), 'duration_days': p["days"], 'description': p["desc"]}
            )
            subs[p["title"]] = s
        return subs

    def _create_payment_methods(self, user):
        methods = []
        for _ in range(random.randint(1, 2)):
            p_type = random.choice(UserPaymentMethod.PAYMENT_TYPE_CHOICES)[0]
            defaults = {
                'masked_card_number': f"**** **** **** {fake.numerify('####')}" if p_type == 'card' else None,
                'card_brand': random.choice(['Visa', 'Mastercard', 'Mir']) if p_type == 'card' else None,
                'card_expiry_month': random.randint(1, 12) if p_type == 'card' else None,
                'card_expiry_year': timezone.now().year + random.randint(1, 5) if p_type == 'card' else None,
            }
            m, _ = UserPaymentMethod.objects.get_or_create(user=user, payment_type=p_type, provider_id=fake.uuid4(), defaults=defaults)
            methods.append(m)
        return methods

    def _create_user_subscription(self, user, subscription, payment_methods):
        is_active = fake.boolean(chance_of_getting_true=70)
        if is_active:
            start = self._make_aware(fake.date_time_between(start_date='-6M', end_date='-1d'))
            end = start + datetime.timedelta(days=subscription.duration_days)
            if end < timezone.now():
                end = timezone.now() + datetime.timedelta(days=random.randint(1, 30))
            canceled = None
        else:
            start = self._make_aware(fake.date_time_between(start_date='-2y', end_date='-7M'))
            end = start + datetime.timedelta(days=subscription.duration_days)
            canceled = self._make_aware(fake.date_time_between(start_date=end, end_date='now'))

        user_sub, _ = UserSubscription.objects.get_or_create(
            user=user, subscription=subscription, start_date=start,
            defaults={'end_date': end, 'is_active': is_active, 'auto_renew': fake.boolean(chance_of_getting_true=40), 'canceled_at': canceled}
        )
        if payment_methods:
            user_sub.payment_methods.set(random.sample(payment_methods, k=min(1, len(payment_methods))))
        return user_sub

    def _create_comments(self, users, chapters, count=40):
        created = 0
        banned = ["badword1", "badword2", "badword3"]
        for _ in range(count):
            u, ch = random.choice(users), random.choice(chapters)
            if Comment.objects.filter(user=u, chapter=ch).exists(): continue
            while True:
                txt = fake.paragraph(nb_sentences=random.randint(1, 4))
                if not any(w in txt.lower() for w in banned): break
            Comment.objects.create(user=u, chapter=ch, text=txt, created_at=self._make_aware(fake.date_time_between(start_date=ch.release_date, end_date='now')), likes_count=random.randint(0, 150), dislikes_count=random.randint(0, 20))
            created += 1
        return created

    def _create_reviews(self, users, chapters, count=30):
        created = 0
        banned = ["badword1", "offensivephrase", "forbidden"]
        for _ in range(count):
            u, ch = random.choice(users), random.choice(chapters)
            if Review.objects.filter(user=u, chapter=ch).exists(): continue
            txt = None
            if fake.boolean(chance_of_getting_true=70):
                while True:
                    t = fake.paragraph(nb_sentences=random.randint(2, 6))
                    if not any(w in t.lower() for w in banned): txt = t; break
            Review.objects.create(user=u, chapter=ch, text=txt, created_at=self._make_aware(fake.date_time_between(start_date=ch.release_date, end_date='now')), likes_count=random.randint(0, 300), dislikes_count=random.randint(0, 30))
            created += 1
        return created

    def _create_ratings(self, users, chapters, count=50):
        created = 0
        for _ in range(count):
            u, ch = random.choice(users), random.choice(chapters)
            if Rating.objects.filter(user=u, chapter=ch).exists(): continue
            Rating.objects.create(user=u, chapter=ch, score=random.randint(1, 10), created_at=self._make_aware(fake.date_time_between(start_date=ch.release_date, end_date='now')))
            created += 1
        return created

    def _create_playlists(self, users, count_range=(1, 3)):
        pls = []
        for u in users[:10]:
            for _ in range(random.randint(*count_range)):
                # ✅ ИСПРАВЛЕНО: Убран slug из создания. Генерируем уникальное title, 
                # чтобы save() модели создал уникальный slug автоматически.
                title = f"{fake.sentence(nb_words=3).rstrip('.')} {random.randint(100, 999)}"
                p = Playlist.objects.create(
                    user=u, title=title,
                    description=fake.paragraph(nb_sentences=2),
                    is_public=fake.boolean(chance_of_getting_true=60),
                    cover_image_url=fake.image_url() if fake.boolean(chance_of_getting_true=40) else None,
                    is_favorite=fake.boolean(chance_of_getting_true=15),
                    created_at=self._make_aware(fake.date_time_between(start_date='-1y', end_date='now'))
                )
                pls.append(p)
        return pls

    def _create_playlist_chapters(self, playlists, chapters):
        added = 0
        for pl in playlists:
            for ch in random.sample(chapters, k=min(random.randint(2, 6), len(chapters))):
                if PlaylistChapter.objects.filter(playlist=pl, chapter=ch).exists(): continue
                PlaylistChapter.objects.create(playlist=pl, chapter=ch, note=fake.sentence() if fake.boolean(chance_of_getting_true=50) else None, added_at=self._make_aware(fake.date_time_between(start_date='-6M', end_date='now')))
                added += 1
        return added

    def _create_view_history(self, users, chapters):
        created = 0
        for u in users:
            for ch in random.sample(chapters, k=min(random.randint(3, 8), len(chapters))):
                if ViewHistory.objects.filter(user=u, chapter=ch).exists(): continue
                ViewHistory.objects.create(user=u, chapter=ch, viewed_at=self._make_aware(fake.date_time_between(start_date=ch.release_date, end_date='now')))
                created += 1
        return created