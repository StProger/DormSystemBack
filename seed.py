"""Seed script: populates database with test data and generates logs."""

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.database import SessionLocal, engine
from app.core.logging_config import setup_logging
from app.core.security import hash_password
from app.models.announcement import Announcement
from app.models.guest_pass import GuestPass, GuestPassStatus
from app.models.notification import Notification, NotificationRecipient
from app.models.receipt_request import ReceiptRequest, ReceiptRequestStatus
from app.models.room import Room
from app.models.room_assessment import RoomAssessment
from app.models.room_resident import RoomResident
from app.models.ticket import Ticket, TicketStatus, TicketType
from app.models.user import User, UserRole

logger = logging.getLogger("dorm.seed")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
now = datetime.now(timezone.utc)


def past(days: int) -> datetime:
    return now - timedelta(days=days)


def rand_past(max_days: int = 60) -> datetime:
    return now - timedelta(days=random.randint(1, max_days), hours=random.randint(0, 23))


PASSWORD_HASH = hash_password("password123")

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
STUDENTS = [
    ("Иванов Иван Иванович", "ivanov@student.ru", "+79001111111"),
    ("Петрова Анна Сергеевна", "petrova@student.ru", "+79002222222"),
    ("Сидоров Алексей Дмитриевич", "sidorov@student.ru", "+79003333333"),
    ("Козлова Мария Александровна", "kozlova@student.ru", "+79004444444"),
    ("Новиков Дмитрий Павлович", "novikov@student.ru", "+79005555555"),
    ("Федорова Елена Викторовна", "fedorova@student.ru", "+79006666666"),
    ("Морозов Артём Николаевич", "morozov@student.ru", "+79007777777"),
    ("Волкова Ольга Андреевна", "volkova@student.ru", "+79008888888"),
    ("Лебедев Кирилл Олегович", "lebedev@student.ru", "+79009999999"),
    ("Соколова Дарья Игоревна", "sokolova@student.ru", "+79010000000"),
    ("Кузнецов Максим Романович", "kuznetsov@student.ru", "+79011111111"),
    ("Попова Виктория Михайловна", "popova@student.ru", "+79012222222"),
    ("Егоров Никита Владимирович", "egorov@student.ru", "+79013333333"),
    ("Белова Алина Юрьевна", "belova@student.ru", "+79014444444"),
    ("Орлов Даниил Геннадьевич", "orlov@student.ru", "+79015555555"),
]

STAFF = [
    ("Смирнова Татьяна Борисовна", "smirnova@dorm.ru", "+79100000001", UserRole.comendant),
    ("Григорьев Павел Петрович", "grigoriev@dorm.ru", "+79100000002", UserRole.comendant),
    ("Васильев Сергей Иванович", "vasiliev@dorm.ru", "+79100000003", UserRole.head),
    ("Николаев Андрей Викторович", "nikolaev@dorm.ru", "+79100000004", UserRole.guard),
    ("Романов Виктор Степанович", "romanov@dorm.ru", "+79100000005", UserRole.guard),
]

ROOMS = [
    ("101", 3), ("102", 3), ("103", 2), ("104", 4),
    ("201", 3), ("202", 3), ("203", 2), ("204", 4),
    ("301", 3), ("302", 3), ("303", 2), ("304", 4),
]

ANNOUNCEMENTS = [
    ("Плановое отключение воды", "10 марта с 09:00 до 18:00 будет отключена горячая вода в связи с профилактическими работами."),
    ("Собрание жильцов", "Приглашаем всех жильцов на общее собрание 15 марта в 19:00 в актовом зале."),
    ("Уборка территории", "Субботник состоится 20 марта. Сбор у главного входа в 10:00."),
    ("Новые правила прохода гостей", "С 1 апреля вводится электронная система гостевых пропусков. Подробности у коменданта."),
    ("Ремонт лифта", "С 12 по 14 марта лифт будет недоступен. Приносим извинения за неудобства."),
    ("Конкурс на лучшую комнату", "Объявляем конкурс чистоты! Проверка комнат — 25 марта. Победители получат призы."),
]

TICKET_DATA = [
    ("Течёт кран в ванной", "Капает вода из крана горячей воды, невозможно закрыть полностью.", TicketType.repair),
    ("Не работает розетка", "Розетка у окна перестала работать, проверял несколько приборов.", TicketType.repair),
    ("Скрипит дверь", "Входная дверь в комнату сильно скрипит при открытии/закрытии.", TicketType.maintenance),
    ("Замена лампочки", "Перегорела лампочка в основном светильнике.", TicketType.maintenance),
    ("Вынос старой мебели", "Прошу вывезти сломанный стул из комнаты.", TicketType.large_item),
    ("Засор в раковине", "Вода в раковине уходит очень медленно.", TicketType.repair),
    ("Шатается стол", "Одна ножка стола расшаталась, стол качается.", TicketType.maintenance),
    ("Не закрывается окно", "Ручка оконной рамы прокручивается, невозможно закрыть окно плотно.", TicketType.repair),
    ("Провести интернет-кабель", "Прошу провести дополнительную ethernet-розетку к рабочему месту.", TicketType.maintenance),
    ("Вынос старого холодильника", "Холодильник сломан, прошу забрать и вывезти.", TicketType.large_item),
]

GUEST_NAMES = [
    "Тихонов Артур Владимирович",
    "Захарова Ксения Дмитриевна",
    "Макаров Роман Сергеевич",
    "Антонова Полина Алексеевна",
    "Степанов Глеб Андреевич",
    "Герасимова Нина Петровна",
    "Павлов Егор Максимович",
    "Крылова Ирина Олеговна",
]

ASSESSMENT_COMMENTS = [
    "Чисто, порядок в комнате.",
    "Небольшой беспорядок на столе.",
    "Отличное состояние, всё аккуратно.",
    "Нужно убрать мусор у двери.",
    "Комната в хорошем состоянии.",
    "Обнаружены повреждения обоев у окна.",
    None,
    None,
]


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------
async def seed() -> None:
    setup_logging()
    logger.info("Starting database seed...")

    async with SessionLocal() as session:
        # Check if data already exists
        result = await session.execute(text("SELECT count(*) FROM users"))
        count = result.scalar()
        if count and count > 1:
            logger.warning("Database already has %d users — skipping seed to avoid duplicates.", count)
            print(f"Database already has {count} users. Delete data first or use a fresh DB.")
            return

        # -- Users --
        admin = User(
            email="admin@example.com",
            password_hash=PASSWORD_HASH,
            role=UserRole.comendant,
            full_name="Администратор Системы",
            phone="+79000000000",
        )
        session.add(admin)

        student_users: list[User] = []
        for full_name, email, phone in STUDENTS:
            u = User(
                email=email,
                password_hash=PASSWORD_HASH,
                role=UserRole.student,
                full_name=full_name,
                phone=phone,
            )
            session.add(u)
            student_users.append(u)

        staff_users: list[User] = []
        for full_name, email, phone, role in STAFF:
            u = User(
                email=email,
                password_hash=PASSWORD_HASH,
                role=role,
                full_name=full_name,
                phone=phone,
            )
            session.add(u)
            staff_users.append(u)

        await session.flush()
        all_users = [admin] + student_users + staff_users
        comendants = [admin] + [u for u in staff_users if u.role == UserRole.comendant]
        guards = [u for u in staff_users if u.role == UserRole.guard]

        logger.info("Created %d users", len(all_users))

        # -- Rooms --
        rooms: list[Room] = []
        for number, capacity in ROOMS:
            r = Room(number=number, capacity=capacity)
            session.add(r)
            rooms.append(r)
        await session.flush()
        logger.info("Created %d rooms", len(rooms))

        # -- Room residents (assign students to rooms) --
        student_idx = 0
        for room in rooms:
            cap = room.capacity or 2
            for _ in range(min(cap, len(student_users) - student_idx)):
                if student_idx >= len(student_users):
                    break
                rr = RoomResident(
                    room_id=room.id,
                    user_id=student_users[student_idx].id,
                    is_active=True,
                    assigned_at=past(random.randint(30, 180)),
                )
                session.add(rr)
                student_idx += 1
        await session.flush()
        logger.info("Assigned %d students to rooms", student_idx)

        # -- Announcements --
        for title, body in ANNOUNCEMENTS:
            a = Announcement(
                title=title,
                body=body,
                created_by=random.choice(comendants).id,
                publish_at=rand_past(30),
            )
            session.add(a)
        await session.flush()
        logger.info("Created %d announcements", len(ANNOUNCEMENTS))

        # -- Tickets --
        tickets: list[Ticket] = []
        for title, desc, ttype in TICKET_DATA:
            creator = random.choice(student_users)
            status = random.choice(list(TicketStatus))
            t = Ticket(
                title=title,
                description=desc,
                type=ttype,
                status=status,
                created_by=creator.id,
                assigned_to=random.choice(comendants).id if status != TicketStatus.in_processing else None,
                admin_comment="Принято в работу." if status == TicketStatus.in_work else (
                    "Выполнено." if status == TicketStatus.done else None
                ),
                closed_at=rand_past(5) if status == TicketStatus.done else None,
            )
            session.add(t)
            tickets.append(t)
        await session.flush()
        logger.info("Created %d tickets", len(tickets))

        # -- Guest passes --
        statuses_pool = [
            GuestPassStatus.pending,
            GuestPassStatus.approved,
            GuestPassStatus.checked_in,
            GuestPassStatus.checked_out,
            GuestPassStatus.rejected,
        ]
        for i, guest_name in enumerate(GUEST_NAMES):
            student = student_users[i % len(student_users)]
            status = statuses_pool[i % len(statuses_pool)]
            planned_from = rand_past(10)
            gp = GuestPass(
                resident_id=student.id,
                guest_full_name=guest_name,
                guest_document=f"45 {random.randint(10, 99)} {random.randint(100000, 999999)}",
                note="В гости" if i % 2 == 0 else "Помощь с переездом",
                planned_from=planned_from,
                planned_to=planned_from + timedelta(hours=random.randint(2, 8)),
                status=status,
                code=f"GP-{uuid.uuid4().hex[:8].upper()}" if status != GuestPassStatus.pending else None,
                code_expires_at=(planned_from + timedelta(hours=12)) if status not in (GuestPassStatus.pending, GuestPassStatus.rejected) else None,
                approved_by=random.choice(comendants).id if status not in (GuestPassStatus.pending,) else None,
                checked_in_at=planned_from + timedelta(minutes=30) if status in (GuestPassStatus.checked_in, GuestPassStatus.checked_out) else None,
                checked_out_at=planned_from + timedelta(hours=4) if status == GuestPassStatus.checked_out else None,
            )
            session.add(gp)
        await session.flush()
        logger.info("Created %d guest passes", len(GUEST_NAMES))

        # -- Room assessments --
        for room in rooms:
            for _ in range(random.randint(1, 3)):
                ra = RoomAssessment(
                    room_id=room.id,
                    score=random.randint(2, 5),
                    comment=random.choice(ASSESSMENT_COMMENTS),
                    assessed_by=random.choice(comendants).id,
                    assessed_at=rand_past(45),
                )
                session.add(ra)
        await session.flush()
        logger.info("Created room assessments")

        # -- Notifications --
        notif_titles = [
            ("Оплата за февраль", "Напоминаем об оплате проживания за февраль до 10 марта."),
            ("Результаты проверки", "Ваша комната прошла проверку. Оценка: 4/5."),
            ("Заявка одобрена", "Ваша заявка на гостевой пропуск одобрена."),
            ("Плановые работы", "В вашем блоке будут проводиться плановые работы 18 марта."),
        ]
        for title, body in notif_titles:
            n = Notification(
                title=title,
                body=body,
                created_by_user_id=random.choice(comendants).id,
            )
            session.add(n)
            await session.flush()

            recipients = random.sample(student_users, k=min(random.randint(3, 8), len(student_users)))
            for student in recipients:
                is_read = random.choice([True, False])
                nr = NotificationRecipient(
                    notification_id=n.id,
                    user_id=student.id,
                    is_read=is_read,
                    read_at=rand_past(5) if is_read else None,
                )
                session.add(nr)
        await session.flush()
        logger.info("Created %d notifications with recipients", len(notif_titles))

        # -- Receipt requests --
        periods = ["01.2026", "02.2026", "12.2025", "11.2025"]
        for i in range(8):
            student = student_users[i % len(student_users)]
            status = random.choice(list(ReceiptRequestStatus))
            rr = ReceiptRequest(
                user_id=student.id,
                period=random.choice(periods),
                comment="Нужна квитанция для бухгалтерии" if i % 3 == 0 else None,
                status=status,
                processed_at=rand_past(5) if status != ReceiptRequestStatus.pending else None,
                processed_by_user_id=random.choice(comendants).id if status != ReceiptRequestStatus.pending else None,
                send_to_email=random.choice([True, False]),
            )
            session.add(rr)
        await session.flush()
        logger.info("Created 8 receipt requests")

        # -- Commit everything --
        await session.commit()
        logger.info("Seed completed successfully!")

    # -- Generate audit-style logs to push to ELK --
    _generate_sample_logs(student_users, comendants, guards, tickets, rooms)


def _generate_sample_logs(
    students: list[User],
    comendants: list[User],
    guards: list[User],
    tickets: list[Ticket],
    rooms: list[Room],
) -> None:
    """Emit sample log messages so they appear in ELK."""
    from app.core.logging_config import user_id_ctx, trace_id_ctx

    events = []

    # Simulate logins
    for u in random.sample(students, k=min(8, len(students))):
        trace_id_ctx.set(uuid.uuid4().hex[:16])
        user_id_ctx.set(str(u.id))
        logging.getLogger("dorm.audit.user_login").info(
            "user_login",
            extra={"event": "user_login", "entity_type": "user", "entity_id": str(u.id)},
        )

    for u in comendants:
        trace_id_ctx.set(uuid.uuid4().hex[:16])
        user_id_ctx.set(str(u.id))
        logging.getLogger("dorm.audit.user_login").info(
            "user_login",
            extra={"event": "user_login", "entity_type": "user", "entity_id": str(u.id)},
        )

    # Simulate ticket creation
    for t in tickets[:5]:
        trace_id_ctx.set(uuid.uuid4().hex[:16])
        user_id_ctx.set(str(t.created_by))
        logging.getLogger("dorm.audit.ticket_created").info(
            "ticket_created",
            extra={"event": "ticket_created", "entity_type": "ticket", "entity_id": str(t.id),
                   "detail": {"title": t.title, "type": t.type.value}},
        )

    # Simulate ticket status changes
    for t in tickets[5:]:
        trace_id_ctx.set(uuid.uuid4().hex[:16])
        user_id_ctx.set(str(t.assigned_to or t.created_by))
        logging.getLogger("dorm.audit.ticket_status_changed").info(
            "ticket_status_changed",
            extra={"event": "ticket_status_changed", "entity_type": "ticket", "entity_id": str(t.id),
                   "detail": {"new_status": t.status.value}},
        )

    # Simulate room assessments
    for room in random.sample(rooms, k=min(5, len(rooms))):
        trace_id_ctx.set(uuid.uuid4().hex[:16])
        user_id_ctx.set(str(random.choice(comendants).id))
        logging.getLogger("dorm.audit.room_assessed").info(
            "room_assessed",
            extra={"event": "room_assessed", "entity_type": "room", "entity_id": str(room.id),
                   "detail": {"room_number": room.number, "score": random.randint(2, 5)}},
        )

    # Simulate guest pass flow
    for guard in guards:
        trace_id_ctx.set(uuid.uuid4().hex[:16])
        user_id_ctx.set(str(guard.id))
        logging.getLogger("dorm.audit.guest_checked_in").info(
            "guest_checked_in",
            extra={"event": "guest_checked_in", "entity_type": "guest_pass",
                   "detail": {"guest_name": random.choice(GUEST_NAMES)}},
        )

    # Simulate some warnings/errors
    trace_id_ctx.set(uuid.uuid4().hex[:16])
    user_id_ctx.set("-")
    logging.getLogger("dorm.http").warning("Slow query detected: GET /api/tickets took 2.3s")
    logging.getLogger("dorm.http").error(
        "Internal server error on POST /api/guest-passes",
        extra={"status_code": 500, "path": "/api/guest-passes"},
    )
    logging.getLogger("dorm.http").warning("Rate limit approached for IP 192.168.1.50")

    logger.info("Generated %d sample log events for ELK", 25)


if __name__ == "__main__":
    asyncio.run(seed())