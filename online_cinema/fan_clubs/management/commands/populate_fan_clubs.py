# fan_clubs/management/commands/seed_fan_clubs.py

import io
from django.db import transaction
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth import get_user_model

from fan_clubs.models import FanClub, FanClubPhoto, FanClubMembership, FanClubApplicationAttachment
from cinema.models import Franchise, Chapter

User = get_user_model()


def get_dummy_image(filename='cover.png'):
    """Генерирует минимальный валидный PNG 1x1 пиксель для ImageField"""
    png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    return ContentFile(png_bytes, name=filename)


def generate_unique_slug(title, model, base_slug=None):
    """Генерирует уникальный slug для модели с проверкой на дубликаты"""
    base = base_slug or slugify(title, allow_unicode=True)
    slug = base
    counter = 1
    while model.objects.filter(slug=slug).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


class Command(BaseCommand):
    help = 'Создаёт 3 детализированных фан-клуба с участниками, заявками и галереями'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('🏰 Начинаем создание 3 детализированных фан-клубов...'))

        with transaction.atomic():
            # ================= 1. ПОЛЬЗОВАТЕЛИ =================
            self.stdout.write('👥 Создаём пользователей...')
            users = self._setup_users()
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано/обновлено: {len(users)} пользователей'))

            # ================= 2. ПРИВЯЗКА К КОНТЕНТУ =================
            self.stdout.write('🎬 Привязываем клубы к франшизам и главам...')
            content = self._setup_content_references()
            if not all(content.values()):
                self.stderr.write(self.style.WARNING('   ⚠️ Некоторые франшизы/главы не найдены. Клубы будут созданы без привязки.'))
            self.stdout.write(self.style.SUCCESS('   ✓ Контент найден'))

            # ================= 3. КОНФИГУРАЦИЯ И СОЗДАНИЕ КЛУБОВ =================
            self.stdout.write('📦 Создаём фан-клубы и участников...')
            created_clubs = self._create_clubs(content, users)
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано клубов: {len(created_clubs)}'))

            # ================= ИТОГ =================
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('✅ ГОТОВО! Созданы 3 фан-клуба с полной структурой:'))
            self.stdout.write('='*60)
            for key, club in created_clubs.items():
                self.stdout.write(f"  🏰 {club.title}")
                self.stdout.write(f"     👥 Участников: {club.get_members_count()} | Админов: {club.get_admins_count()}")
                self.stdout.write(f"     🖼️ Фото в галерее: {club.get_photos_count()}")
                self.stdout.write(f"     📝 Ожидают проверки: {club.memberships.filter(status='pending').count()}")
            
            self.stdout.write('-'*60)
            self.stdout.write(f"📎 Всего вложений в заявках: {FanClubApplicationAttachment.objects.count()}")
            self.stdout.write(f"🖼️ Всего фото в галереях: {FanClubPhoto.objects.count()}")
            self.stdout.write(f"🔗 Всего членств: {FanClubMembership.objects.count()}")
            self.stdout.write('='*60)

    # ================= ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =================

    def _setup_users(self):
        users_data = [
            ("admin_arthur", "Артур", "Вайс", "Создатель и администратор комьюнити"),
            ("user_bella", "Белла", "Свон", "Фанат фэнтези и книжных вселенных"),
            ("user_charlie", "Чарли", "Хант", "Исследователь лора и теорий"),
            ("user_diana", "Диана", "Принс", "Коллекционер мерча и артов"),
            ("user_edward", "Эдвард", "Каллен", "Косплеер и фотограф"),
            ("user_fiona", "Фиона", "Галлахер", "Сценарист-любитель"),
            ("user_george", "Джордж", "Мартин", "Аналитик кино и комиксов"),
            ("user_hannah", "Ханна", "Монтана", "Художник и дизайнер"),
            ("user_ivan", "Иван", "Петров", "Монтажёр и видеограф"),
            ("user_julia", "Юлия", "Соколова", "Переводчик фан-фиков"),
        ]
        users = {}
        for uname, fname, lname, desc in users_data:
            u, _ = User.objects.get_or_create(
                username=uname,
                defaults={
                    "first_name": fname, "last_name": lname,
                    "description": desc, "email": f"{uname}@example.com",
                    "is_active": True, "login_code": f"code_{uname}"
                }
            )
            users[uname] = u
        return users

    def _setup_content_references(self):
        return {
            'hp_franchise': Franchise.objects.filter(title="Гарри Поттер").first(),
            'lotr_franchise': Franchise.objects.filter(title="Властелин колец").first(),
            'tdk_franchise': Franchise.objects.filter(title="Тёмный рыцарь (Трилогия)").first(),
            'hp_ch1': Chapter.objects.filter(title__icontains="философский").first(),
            'lotr_ch1': Chapter.objects.filter(title__icontains="Братство").first(),
            'tdk_ch2': Chapter.objects.filter(title__icontains="Тёмный рыцарь").first(),
        }

    def _create_clubs(self, content, users):
        clubs_config = [
            {
                "key": "phoenix",
                "title": "Орден Феникса | Harry Potter",
                "desc": "Закрытое сообщество для глубокого изучения вселенной Гарри Поттера. Обсуждаем лор, теории, делимся фан-артом и косплеем. Уважение к канону и участникам — главный закон.",
                "franchise": content['hp_franchise'], "chapter": content['hp_ch1'],
                "creator": users["admin_arthur"],
                "requirements": "1. Возраст 16+\n2. Знание лора минимум на уровне прочтения 3 книг/просмотра фильмов.\n3. Готовность делиться знаниями и уважать другие точки зрения.",
                "questions": [
                    {"id": "q1", "text": "Ваш любимый факультет Хогвартса и почему?"},
                    {"id": "q2", "text": "Сколько раз вы перечитывали книги или пересматривали фильмы?"},
                    {"id": "q3", "text": "Какое заклинание вы бы использовали в реальной жизни и зачем?"}
                ],
                "max_app_photos": 3, "max_club_photos": 20,
                "members": [
                    {"user": "user_bella", "role": "admin", "status": "approved", "answers": {"q1": "Когтевран", "q2": "5 раз", "q3": "Акцио (для поиска пультов)"}},
                    {"user": "user_charlie", "role": "member", "status": "approved", "answers": {"q1": "Пуффендуй", "q2": "3 раза", "q3": "Люмос"}},
                    {"user": "user_diana", "role": "member", "status": "pending", "answers": {"q1": "Слизерин", "q2": "2 раза", "q3": "Обливиэйт"}},
                    {"user": "user_edward", "role": "member", "status": "rejected", "answers": {"q1": "Гриффиндор", "q2": "1 раз", "q3": "Экспеллиармус"}}
                ]
            },
            {
                "key": "ring",
                "title": "Хранители Кольца | Средиземье",
                "desc": "Клуб для ценителей творчества Дж.Р.Р. Толкина. Анализируем книги, сравниваем с экранизациями, изучаем эльфийские языки и карты Средиземья.",
                "franchise": content['lotr_franchise'], "chapter": content['lotr_ch1'],
                "creator": users["user_fiona"],
                "requirements": "Любовь к детализированным мирам. Приветствуется чтение 'Сильмариллиона'. Спойлеры только под тегами.",
                "questions": [
                    {"id": "q1", "text": "Что вам ближе: книги Толкина или фильмы Джексона?"},
                    {"id": "q2", "text": "Кто ваш любимый персонаж и какая его сцена запомнилась больше всего?"}
                ],
                "max_app_photos": 2, "max_club_photos": 15,
                "members": [
                    {"user": "user_george", "role": "admin", "status": "approved", "answers": {"q1": "Книги, безусловно", "q2": "Гэндальф Серый на мосту Кхазад-Дума"}},
                    {"user": "user_hannah", "role": "member", "status": "approved", "answers": {"q1": "Фильмы за визуал", "q2": "Арагорн и коронация"}},
                    {"user": "user_ivan", "role": "member", "status": "pending", "answers": {"q1": "Обожаю оба варианта", "q2": "Фродо и Сэм на Роковой Горе"}},
                    {"user": "user_julia", "role": "member", "status": "banned", "answers": {"q1": "Книги", "q2": "Бильбо"}}
                ]
            },
            {
                "key": "gotham",
                "title": "Рыцари Готэма | Тёмный Рыцарь",
                "desc": "Сообщество для анализа кинематографа Нолана, комиксов DC и философских тем франшизы. Обсуждаем мораль, визуальный стиль и влияние на поп-культуру.",
                "franchise": content['tdk_franchise'], "chapter": content['tdk_ch2'],
                "creator": users["user_bella"],
                "requirements": "Интерес к супергероике в реалистичном ключе. Запрещены токсичные споры 'Marvel vs DC'.",
                "questions": [
                    {"id": "q1", "text": "Кто ваш любимый антагонист из вселенной Бэтмена?"},
                    {"id": "q2", "text": "Какая часть трилогии Нолана для вас лучшая и почему?"}
                ],
                "max_app_photos": 4, "max_club_photos": 25,
                "members": [
                    {"user": "admin_arthur", "role": "member", "status": "approved", "answers": {"q1": "Джокер (Хит Леджер)", "q2": "Тёмный рыцарь"}},
                    {"user": "user_charlie", "role": "admin", "status": "approved", "answers": {"q1": "Бэйн", "q2": "Начало"}},
                    {"user": "user_diana", "role": "member", "status": "approved", "answers": {"q1": "Загадочник", "q2": "Возрождение легенды"}},
                    {"user": "user_fiona", "role": "member", "status": "pending", "answers": {"q1": "Пингвин", "q2": "Тёмный рыцарь"}},
                    {"user": "user_george", "role": "member", "status": "rejected", "answers": {"q1": "Крокок", "q2": "Начало"}}
                ]
            }
        ]

        created_clubs = {}

        for cfg in clubs_config:
            # ✅ ИСПРАВЛЕНО: Генерируем уникальный slug явно
            slug = generate_unique_slug(cfg['title'], FanClub)
            
            # ✅ ИСПРАВЛЕНО: Используем get_or_create с slug в lookup + defaults
            club, created = FanClub.objects.get_or_create(
                slug=slug,  # lookup по slug, а не по title
                defaults={
                    "title": cfg['title'],
                    "description": cfg['desc'],
                    "cover_photo": get_dummy_image(f"cover_{cfg['key']}.png"),
                    "franchise": cfg['franchise'],
                    "chapter": cfg['chapter'],
                    "created_by": cfg['creator'],
                    "requirements_text": cfg['requirements'],
                    "application_questions": cfg['questions'],
                    "max_application_photos": cfg['max_app_photos'],
                    "max_club_photos": cfg['max_club_photos'],
                    "is_active": True
                }
            )
            created_clubs[cfg['key']] = club

            # Пропускаем обработку участников, если клуб уже существовал (чтобы не дублировать)
            if not created:
                continue

            # 3.2 Обрабатываем участников
            for m_cfg in cfg['members']:
                user = users[m_cfg['user']]
                
                membership, _ = FanClubMembership.objects.get_or_create(
                    user=user, club=club,
                    defaults={
                        "role": m_cfg['role'],
                        "status": "pending",
                        "application_data": m_cfg['answers']
                    }
                )

                # 3.3 Создаём вложения к заявке (1-2 фото)
                num_attachments = 1 if m_cfg['status'] == 'rejected' else 2
                for i in range(num_attachments):
                    FanClubApplicationAttachment.objects.create(
                        membership=membership,
                        photo=get_dummy_image(f"app_{cfg['key']}_{m_cfg['user']}_{i}.png"),
                        caption=f"Фан-арт / Косплей от {user.username}"
                    )

                # 3.4 Модерируем заявку через методы модели
                moderator = cfg['creator']
                
                if m_cfg['status'] == 'approved':
                    membership.approve(moderator)
                elif m_cfg['status'] == 'rejected':
                    membership.reject(moderator, "Недостаточно раскрыты ответы на вопросы заявки.")
                elif m_cfg['status'] == 'banned':
                    membership.status = 'banned'
                    membership.reviewed_by = moderator
                    membership.review_comment = "Нарушение правил комьюнити в тестовом режиме."
                    membership.joined_at = timezone.now()
                    membership.save(update_fields=['status', 'reviewed_by', 'review_comment', 'joined_at'])
                    membership.delete_application_photos()
                
                # 3.5 Переносим 1 фото из одобренной заявки в галерею клуба
                if m_cfg['status'] == 'approved':
                    att_to_move = membership.application_attachments.first()
                    if att_to_move and club.can_add_club_photo():
                        att_to_move.move_to_club_gallery(
                            caption=f"Галерея клуба: работа от {user.username}",
                            uploaded_by=moderator
                        )

        return created_clubs