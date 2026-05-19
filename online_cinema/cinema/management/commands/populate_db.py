import random
from datetime import date, timedelta, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import IntegrityError
from faker import Faker

# 🔔 Замените 'your_app' на фактическое имя вашего приложения
from cinema.models import (
    User,
    UserPaymentMethod,
    Subscription,
    UserSubscription,
    Genre,
    Franchise,
    Chapter,
    Episode,
    Person,
    ChapterPersonRole,
    Comment,
    Review,
    Rating,
    Playlist,
    PlaylistChapter,
    ViewHistory,
)

# Инициализация Faker с русской локализацией
fake = Faker("ru_RU")


class Command(BaseCommand):
    help = "Автоматическое заполнение базы данных тестовыми данными через Faker"

    def handle(self, *args, **kwargs):
        # Очистка (раскомментируйте, если нужно сбрасывать БД перед каждым запуском)
        # ViewHistory.objects.all().delete()
        # PlaylistChapter.objects.all().delete()
        # Playlist.objects.all().delete()
        # ... и т.д.
        fake.unique.clear()  # Сброс внутреннего счётчика уникальности Faker
        self.stdout.write("🚀 Начинаем генерацию тестовых данных...")

        # Порядок важен из-за зависимостей (Foreign Keys)
        self.create_genres(15)
        self.create_subscriptions(4)
        self.create_users(25)
        self.create_payment_methods(40)
        self.create_persons(30)
        self.create_franchises(8)
        self.create_chapters(25)
        self.create_episodes(60)
        self.create_chapter_roles(80)
        self.create_playlists(20)
        self.create_playlist_chapters(50)
        self.create_comments(40)
        self.create_reviews(30)
        self.create_ratings(50)
        self.create_user_subscriptions(15)
        self.create_view_histories(60)

        self.stdout.write(self.style.SUCCESS("✅ База данных успешно заполнена!"))

    # ==========================================
    # Вспомогательные методы создания объектов
    # ==========================================

    def create_genres(self, count):
        self.stdout.write("📚 Генерация жанров...")
        for _ in range(count):
            try:
                Genre.objects.create(name=fake.unique.word().capitalize())
            except IntegrityError:
                pass  # Пропускаем дубли

    def create_subscriptions(self, count):
        self.stdout.write("💳 Генерация типов подписок...")
        titles = ["Базовый", "Стандарт", "Премиум", "Семейный"]
        for i in range(min(count, len(titles))):
            Subscription.objects.create(
                title=titles[i],
                price_usd=Decimal(f"{random.uniform(5.99, 19.99):.2f}"),
                duration_days=random.choice([30, 90, 180, 365]),
                description=fake.sentence(),
            )

    def create_users(self, count):
        self.stdout.write("👤 Генерация пользователей...")
        for _ in range(count):
            try:
                user = User.objects.create_user(
                    username=fake.unique.user_name(),
                    email=fake.unique.email(),
                    password="testpass123",  # Хэшируется автоматически через create_user
                )
                user.profile_pic = fake.image_url() if random.random() > 0.5 else None
                user.description = (
                    fake.text(max_nb_chars=200) if random.random() > 0.3 else ""
                )
                user.login_code = f"{random.randint(100000, 999999)}"
                user.save(update_fields=["profile_pic", "description", "login_code"])
            except IntegrityError:
                pass

    def create_payment_methods(self, count):
        self.stdout.write("💰 Генерация способов оплаты...")
        users = list(User.objects.all())
        if not users:
            return
        for _ in range(count):
            try:
                UserPaymentMethod.objects.create(
                    user=random.choice(users),
                    payment_type=random.choice(
                        [c[0] for c in UserPaymentMethod.PAYMENT_TYPE_CHOICES]
                    ),
                    provider_id=fake.uuid4(),
                    masked_card_number=f"**** **** **** {fake.random_number(digits=4)}",
                    card_brand=random.choice(["Visa", "MasterCard", "Mir"]),
                    card_expiry_month=random.randint(1, 12),
                    card_expiry_year=random.randint(
                        timezone.now().year, timezone.now().year + 5
                    ),
                )
            except IntegrityError:
                pass

    def create_persons(self, count):
        self.stdout.write("🎭 Генерация персон...")
        for _ in range(count):
            Person.objects.create(
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                birth_date=fake.date_of_birth(minimum_age=18, maximum_age=80),
                country=fake.country(),
                photo_url=fake.image_url() if random.random() > 0.4 else None,
                biography=fake.text(max_nb_chars=500) if random.random() > 0.3 else "",
            )

    def create_franchises(self, count):
        self.stdout.write("🏰 Генерация франшиз...")
        for _ in range(count):
            try:
                Franchise.objects.create(
                    title=fake.unique.sentence(nb_words=3).rstrip(".")
                )
            except IntegrityError:
                pass

    def create_chapters(self, count):
        self.stdout.write("📖 Генерация глав...")
        franchises = list(Franchise.objects.all())
        genres = list(Genre.objects.all())
        subscriptions = list(Subscription.objects.all())
        if not franchises:
            return

        used_chapter_nums = {}

        for _ in range(count):
            try:
                franchise = random.choice(franchises)
                if franchise not in used_chapter_nums:
                    used_chapter_nums[franchise] = set()

                while True:
                    num = random.randint(1, 50)
                    if num not in used_chapter_nums[franchise]:
                        used_chapter_nums[franchise].add(num)
                        break

                # Дата выхода только в прошлом (требование clean())
                release = fake.date_between(start_date="-3y", end_date="-1d")

                chapter = Chapter.objects.create(
                    franchise=franchise,
                    chapter_number=num,
                    title=fake.sentence(nb_words=4).rstrip("."),
                    description=fake.paragraph(nb_sentences=3),
                    release_date=release,
                    content_type=random.choice(
                        [c[0] for c in Chapter.CONTENT_TYPE_CHOICES]
                    ),
                    age_rating=random.randint(
                        1, 21
                    ),  # 🔥 ИСПРАВЛЕНО: 0 считался пустым в вашей clean()
                    country=fake.country(),
                    rating_cache=round(random.uniform(1.0, 10.0), 1),
                    view_count=random.randint(0, 50000),
                    poster_image=fake.image_url() if random.random() > 0.2 else None,
                    trailer_url=fake.url(),
                    required_subscription=random.choice(subscriptions + [None]),
                )
                # M2M связь
                chapter.genres.add(
                    *random.sample(genres, k=min(len(genres), random.randint(1, 3)))
                )
            except IntegrityError:
                continue

    def create_episodes(self, count):
        self.stdout.write("🎬 Генерация эпизодов...")
        chapters = list(Chapter.objects.all())
        used_ep_nums = {}
        for _ in range(count):
            try:
                chapter = random.choice(chapters)
                if chapter not in used_ep_nums:
                    used_ep_nums[chapter] = set()

                while True:
                    num = random.randint(1, 20)
                    if num not in used_ep_nums[chapter]:
                        used_ep_nums[chapter].add(num)
                        break

                Episode.objects.create(
                    chapter=chapter,
                    episode_number=num,
                    title=fake.unique.word().capitalize(),
                    video_file=fake.file_path(extension="mp4"),
                    duration=timedelta(minutes=random.randint(15, 120)),
                    release_date=fake.date_between(start_date="-2y", end_date="-1d"),
                    thumbnail_img=fake.image_url(),
                )
            except IntegrityError:
                continue

    def create_chapter_roles(self, count):
        self.stdout.write("🎭 Генерация ролей в главах...")
        chapters = list(Chapter.objects.all())
        persons = list(Person.objects.all())
        roles = [c[0] for c in ChapterPersonRole.ROLE_CHOICES]

        for _ in range(count):
            try:
                ChapterPersonRole.objects.create(
                    chapter=random.choice(chapters),
                    person=random.choice(persons),
                    role=random.choice(roles),
                )
            except IntegrityError:
                pass  # unique_together: chapter, person, role

    def create_playlists(self, count):
        self.stdout.write("📂 Генерация плейлистов...")
        users = list(User.objects.all())
        if not users:
            return

        for _ in range(count):
            try:
                # Явно генерируем уникальный слаг, чтобы обойти конфликты slugify
                unique_slug = fake.unique.slug()

                Playlist.objects.create(
                    user=random.choice(users),
                    title=fake.sentence(nb_words=3).rstrip("."),
                    description=fake.text(max_nb_chars=150),
                    is_public=random.choice([True, False]),
                    cover_image_url=fake.image_url(),
                    is_favorite=random.choice([True, False]),
                    slug=unique_slug,  # Переопределяем автогенерацию из save()
                )
            except IntegrityError:
                # Если слаг уже есть в БД (например, при повторном запуске), пропускаем
                continue

    def create_playlist_chapters(self, count):
        self.stdout.write("🔗 Связка плейлистов и глав...")
        playlists = list(Playlist.objects.all())
        chapters = list(Chapter.objects.all())
        used_pairs = set()

        for _ in range(count):
            p = random.choice(playlists)
            c = random.choice(chapters)
            pair = (p.id, c.id)
            if pair in used_pairs:
                continue
            used_pairs.add(pair)

            try:
                PlaylistChapter.objects.create(
                    playlist=p,
                    chapter=c,
                    note=fake.sentence() if random.random() > 0.7 else "",
                )
            except IntegrityError:
                pass

    def _create_unique_user_chapter_pairs(self, count, model_cls, text_field="text"):
        """Универсальный метод для Comment, Review, Rating"""
        users = list(User.objects.all())
        chapters = list(Chapter.objects.all())
        used_pairs = set()

        for _ in range(count):
            u = random.choice(users)
            c = random.choice(chapters)
            pair = (u.id, c.id)
            if pair in used_pairs:
                continue
            used_pairs.add(pair)

            try:
                obj = model_cls(user=u, chapter=c)
                if hasattr(obj, "score"):
                    obj.score = random.randint(1, 10)
                else:
                    # Избегаем запрещённых слов из clean()
                    obj.text = fake.paragraph(nb_sentences=2)
                obj.save()
            except IntegrityError:
                pass

    def create_comments(self, count):
        self.stdout.write("💬 Генерация комментариев...")
        self._create_unique_user_chapter_pairs(count, Comment)

    def create_reviews(self, count):
        self.stdout.write("⭐ Генерация отзывов...")
        self._create_unique_user_chapter_pairs(count, Review)

    def create_ratings(self, count):
        self.stdout.write("📊 Генерация оценок...")
        self._create_unique_user_chapter_pairs(count, Rating)

    def create_user_subscriptions(self, count):
        self.stdout.write("📦 Генерация подписок пользователей...")
        users = list(User.objects.all())
        subs = list(Subscription.objects.all())
        pms = list(UserPaymentMethod.objects.all())

        for _ in range(count):
            try:
                start = fake.date_time_this_year()
                us = UserSubscription.objects.create(
                    user=random.choice(users),
                    subscription=random.choice(subs),
                    start_date=start,
                    is_active=random.choice([True, False]),
                    auto_renew=random.choice([True, False]),
                    canceled_at=(
                        start + timedelta(days=random.randint(1, 30))
                        if random.random() > 0.8
                        else None
                    ),
                )
                # M2M связь
                if pms:
                    us.payment_methods.add(
                        *random.sample(pms, k=min(len(pms), random.randint(1, 2)))
                    )
            except IntegrityError:
                pass

    def create_view_histories(self, count):
        self.stdout.write("👁 Генерация истории просмотров...")
        users = list(User.objects.all())
        chapters = list(Chapter.objects.all())
        used_pairs = set()

        for _ in range(count):
            u = random.choice(users)
            c = random.choice(chapters)
            pair = (u.id, c.id)
            if pair in used_pairs:
                continue
            used_pairs.add(pair)

            try:
                ViewHistory.objects.create(
                    user=u,
                    chapter=c,
                    viewed_at=fake.date_time_between(start_date="-30d", end_date="now"),
                )
            except IntegrityError:
                pass
