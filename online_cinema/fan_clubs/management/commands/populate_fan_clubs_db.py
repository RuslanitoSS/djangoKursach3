import random
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import IntegrityError
from django.conf import settings
from faker import Faker
from django.contrib.auth import get_user_model

# 🔔 ЗАМЕНИТЕ ИМЕНА ПРИЛОЖЕНИЙ НА РЕАЛЬНЫЕ
from cinema.models import Franchise, Chapter
from fan_clubs.models import FanClub, FanClubPhoto, FanClubMembership, FanClubApplicationAttachment

User = get_user_model()
fake = Faker('ru_RU')


def _get_dummy_image():
    """Создаёт минимальное JPEG-изображение в памяти для тестовых полей ImageField"""
    image = Image.new('RGB', (100, 100), color='white')
    buffer = BytesIO()
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(
        name=f"dummy_{fake.uuid4()}.jpg",
        content=buffer.read(),
        content_type='image/jpeg'
    )


class Command(BaseCommand):
    help = 'Автоматическое заполнение БД тестовыми данными для фан-клубов'

    def handle(self, *args, **kwargs):
        fake.unique.clear()
        self.stdout.write('🚀 Начинаем генерацию данных для фан-клубов...')

        self.create_fan_clubs(15)
        self.create_fan_club_photos(40)
        self.create_fan_club_memberships(30)
        self.create_application_attachments(50)

        self.stdout.write(self.style.SUCCESS('✅ База данных успешно заполнена!'))

    # ==========================================
    # Вспомогательные методы
    # ==========================================

    def create_fan_clubs(self, count):
        self.stdout.write('📚 Генерация фан-клубов...')
        users = list(User.objects.all())
        franchises = list(Franchise.objects.all())
        chapters = list(Chapter.objects.all())
        if not users:
            self.stdout.write(self.style.WARNING('⚠️ Нет пользователей. Пропускаю.'))
            return

        for _ in range(count):
            try:
                FanClub.objects.create(
                    title=fake.sentence(nb_words=3).rstrip('.'),
                    description=fake.paragraph(nb_sentences=3),
                    cover_photo=None,  # Опциональное поле, оставляем пустым
                    slug=fake.unique.slug(),
                    franchise=random.choice(franchises + [None]),
                    chapter=random.choice(chapters + [None]),
                    created_by=random.choice(users),
                    requirements_text=fake.text(max_nb_chars=150) if random.random() > 0.5 else '',
                    application_questions=[
                        {"id": "q1", "text": f"{fake.sentence(nb_words=4)}?"},
                        {"id": "q2", "text": f"{fake.sentence(nb_words=5)}?"}
                    ] if random.random() > 0.3 else [],
                    max_application_photos=random.randint(1, 5),
                    max_club_photos=random.randint(5, 30),
                    allowed_file_types="jpg,jpeg,png",
                    max_file_size_mb=random.choice([2, 5, 10]),
                    is_active=random.choice([True, False])
                )
            except IntegrityError:
                pass

    def create_fan_club_photos(self, count):
        self.stdout.write('🖼 Генерация фото клубов...')
        clubs = list(FanClub.objects.all())
        users = list(User.objects.all())
        if not clubs or not users:
            return

        for _ in range(count):
            FanClubPhoto.objects.create(
                club=random.choice(clubs),
                photo=_get_dummy_image(),  # Обязательное поле, генерируем заглушку
                caption=fake.sentence(nb_words=5) if random.random() > 0.3 else '',
                uploaded_by=random.choice(users)
            )

    def create_fan_club_memberships(self, count):
        self.stdout.write('👥 Генерация членств в клубах...')
        users = list(User.objects.all())
        clubs = list(FanClub.objects.all())
        if not users or not clubs:
            return

        used_pairs = set()
        for _ in range(count):
            u = random.choice(users)
            c = random.choice(clubs)
            if (u.id, c.id) in used_pairs:
                continue
            used_pairs.add((u.id, c.id))

            # Логика статусов и ролей с учётом clean() модели
            status = random.choice(['pending', 'approved', 'rejected', 'banned'])
            role = 'admin' if (status == 'approved' and random.random() > 0.8) else 'member'

            joined = timezone.now() if status == 'approved' else None
            reviewer = random.choice(users) if status != 'pending' else None

            try:
                FanClubMembership.objects.create(
                    user=u,
                    club=c,
                    role=role,
                    status=status,
                    application_data={"q1": fake.sentence(), "q2": fake.sentence()} if random.random() > 0.4 else {},
                    reviewed_by=reviewer,
                    review_comment=fake.sentence() if status in ['approved', 'rejected'] else '',
                    joined_at=joined
                )
            except IntegrityError:
                pass

    def create_application_attachments(self, count):
        self.stdout.write('📎 Генерация вложений заявок...')
        memberships = list(FanClubMembership.objects.all())
        if not memberships:
            return

        for _ in range(count):
            membership = random.choice(memberships)
            moved = random.choice([True, False])
            
            # Если фото перенесено в галерею, создаём и целевое фото
            club_photo = FanClubPhoto.objects.create(
                club=membership.club,
                photo=_get_dummy_image(),
                caption=fake.sentence(nb_words=4),
                uploaded_by=membership.reviewed_by or membership.user
            ) if moved else None

            try:
                FanClubApplicationAttachment.objects.create(
                    membership=membership,
                    photo=_get_dummy_image(),  # Обязательное поле
                    caption=fake.sentence(nb_words=4) if random.random() > 0.5 else '',
                    moved_to_club_gallery=moved,
                    club_photo=club_photo
                )
            except IntegrityError:
                pass