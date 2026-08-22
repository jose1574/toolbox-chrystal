# coding: utf-8
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import and_, text
from sqlalchemy.orm import foreign
import json


# Cambia esto si es necesario:
from app import db


class AccountAccounting(db.Model):
    __tablename__ = "account_accounting"
    __table_args__ = {"schema": "public", "extend_existing": True}
    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class AdditionalFieldsConfig(db.Model):
    __tablename__ = "additional_fields_config"
    __table_args__ = {"schema": "public", "extend_existing": True}

    module = db.Column(db.Integer, primary_key=True, nullable=False)
    code = db.Column(db.String, primary_key=True, nullable=False)
    field_type = db.Column(db.Integer)
    field_label = db.Column(db.String)
    default_value = db.Column(db.String)
    visible = db.Column(db.Boolean)
    field_order = db.Column(db.Integer)
    internal_use = db.Column(db.Boolean)


class AditionalDataEntity(db.Model):
    __tablename__ = "aditional_data_entity"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    description = db.Column(db.String)
    table_name = db.Column(db.String)
    index_column = db.Column(db.Integer)
    module = db.Column(db.String)


class AditionalDataEntityDetail(db.Model):
    __tablename__ = "aditional_data_entity_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.aditional_data_entity.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    field = db.Column(db.String)
    field_label = db.Column(db.String)
    column_type = db.Column(db.String)
    width = db.Column(db.Integer)
    visible = db.Column(db.Boolean)
    index_column = db.Column(db.Integer)
    field_configuration = db.Column(db.String)
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )

    aditional_data_entity = db.relationship(
        "AditionalDataEntity",
        primaryjoin="AditionalDataEntityDetail.main_correlative == AditionalDataEntity.correlative",
        backref="aditional_data_entity_details",
    )


class AditionalDataEntityRel(db.Model):
    __tablename__ = "aditional_data_entity_rel"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_line = db.Column(
        db.ForeignKey(
            "public.aditional_data_entity.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    table_name = db.Column(db.String)
    module = db.Column(db.String, primary_key=True, nullable=False)

    aditional_data_entity = db.relationship(
        "AditionalDataEntity",
        primaryjoin="AditionalDataEntityRel.main_line == AditionalDataEntity.correlative",
        backref="aditional_data_entity_rels",
    )


class ArchingBox(db.Model):
    __tablename__ = "arching_box"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    document_no = db.Column(db.String)
    open_date = db.Column(db.Date)
    close_date = db.Column(db.Date)
    open_user = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    close_user = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    box_user = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    open_description = db.Column(db.String)
    close_description = db.Column(db.String)
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    open_hour = db.Column(db.Time)
    close_hour = db.Column(db.Time)
    status = db.Column(db.String)

    user = db.relationship(
        "User",
        primaryjoin="ArchingBox.box_user == User.code",
        backref="user_user_arching_boxes",
    )
    user1 = db.relationship(
        "User",
        primaryjoin="ArchingBox.close_user == User.code",
        backref="user_user_arching_boxes_0",
    )
    user2 = db.relationship(
        "User",
        primaryjoin="ArchingBox.open_user == User.code",
        backref="user_user_arching_boxes_1",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="ArchingBox.station == Station.code",
        backref="arching_boxes",
    )


class ArchingBoxDetail(db.Model):
    __tablename__ = "arching_box_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.arching_box.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    type_operation = db.Column(db.String)
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    detail_amount = db.Column(db.Double(53))
    count_amount = db.Column(db.Double(53))
    difference = db.Column(db.Double(53))
    description = db.Column(db.String)
    initial_amount = db.Column(db.Double(53))

    coin = db.relationship(
        "Coin",
        primaryjoin="ArchingBoxDetail.coin_code == Coin.code",
        backref="arching_box_details",
    )
    arching_box = db.relationship(
        "ArchingBox",
        primaryjoin="ArchingBoxDetail.main_correlative == ArchingBox.correlative",
        backref="arching_box_details",
    )


class AreaSale(db.Model):
    __tablename__ = "area_sales"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class BackupsLog(db.Model):
    __tablename__ = "backups_log"
    __table_args__ = {"schema": "public", "extend_existing": True}

    id = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    emission_date = db.Column(db.Date)
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    register_hour = db.Column(db.Time)

    user = db.relationship(
        "User", primaryjoin="BackupsLog.user_code == User.code", backref="backups_logs"
    )


class BankAccount(db.Model):
    __tablename__ = "bank_account"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    bank = db.Column(db.String)
    account_accounting = db.Column(
        db.ForeignKey(
            "public.account_accounting.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    last_check_number = db.Column(db.Integer)
    conciliation_period = db.Column(db.String)
    initial_balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    credits = db.Column(db.Double(53), server_default=db.FetchedValue())
    debits = db.Column(db.Double(53), server_default=db.FetchedValue())
    deferred_credits = db.Column(db.Double(53), server_default=db.FetchedValue())
    deferred_debits = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    available_balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    movil_payment = db.Column(db.Boolean, server_default=db.FetchedValue())
    movil_payment_id = db.Column(db.String, server_default=db.FetchedValue())
    movil_payment_phone = db.Column(db.String, server_default=db.FetchedValue())

    account_accounting1 = db.relationship(
        "AccountAccounting",
        primaryjoin="BankAccount.account_accounting == AccountAccounting.code",
        backref="bank_accounts",
    )
    coin1 = db.relationship(
        "Coin", primaryjoin="BankAccount.coin == Coin.code", backref="bank_accounts"
    )


class BankAccountTax(db.Model):
    __tablename__ = "bank_account_taxes"
    __table_args__ = {"schema": "public", "extend_existing": True}

    line = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    bank_account_code = db.Column(
        db.ForeignKey(
            "public.bank_account.code", ondelete="CASCADE", onupdate="CASCADE"
        )
    )
    description = db.Column(db.String)
    status = db.Column(db.Boolean)
    tax_type = db.Column(db.Integer)
    tax_value = db.Column(db.Double(53))
    apply_values_higher_to = db.Column(db.Double(53))
    destiny_bank = db.Column(db.Integer)
    account_accountin_code = db.Column(
        db.ForeignKey(
            "public.account_accounting.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    transaction_type = db.Column(db.Integer)
    transaction_description = db.Column(db.String)

    account_accounting = db.relationship(
        "AccountAccounting",
        primaryjoin="BankAccountTax.account_accountin_code == AccountAccounting.code",
        backref="bank_account_taxes",
    )
    bank_account = db.relationship(
        "BankAccount",
        primaryjoin="BankAccountTax.bank_account_code == BankAccount.code",
        backref="bank_account_taxes",
    )


class BankConciliation(db.Model):
    __tablename__ = "bank_conciliation"
    __table_args__ = (
        db.UniqueConstraint("bank_account", "period_conciliation"),
        {"schema": "public", "extend_existing": True},
    )

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    bank_account = db.Column(
        db.ForeignKey(
            "public.bank_account.code", ondelete="CASCADE", onupdate="CASCADE"
        )
    )
    period_conciliation = db.Column(db.String)
    register_date = db.Column(db.Date)
    user_code = db.Column(db.String)
    initial_balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    credits = db.Column(db.Double(53), server_default=db.FetchedValue())
    debits = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    bank_balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance_difference = db.Column(db.Double(53), server_default=db.FetchedValue())
    deposits_count = db.Column(db.Integer, server_default=db.FetchedValue())
    deposits_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    transfers_received_count = db.Column(db.Integer, server_default=db.FetchedValue())
    transfers_received_amount = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    transfers_made_count = db.Column(db.Integer, server_default=db.FetchedValue())
    transfers_made_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_note_count = db.Column(db.Integer, server_default=db.FetchedValue())
    credit_note_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    debit_note_count = db.Column(db.Integer, server_default=db.FetchedValue())
    debit_note_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    checks_count = db.Column(db.Integer, server_default=db.FetchedValue())
    checks_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    deposits_count_transit = db.Column(db.Integer, server_default=db.FetchedValue())
    deposits_amount_transit = db.Column(db.Double(53), server_default=db.FetchedValue())
    transfers_received_count_transit = db.Column(
        db.Integer, server_default=db.FetchedValue()
    )
    transfers_received_amount_transit = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    transfers_made_count_transit = db.Column(
        db.Integer, server_default=db.FetchedValue()
    )
    transfers_made_amount_transit = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    credit_note_count_transit = db.Column(db.Integer, server_default=db.FetchedValue())
    credit_note_amount_transit = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    debit_note_count_transit = db.Column(db.Integer, server_default=db.FetchedValue())
    debit_note_amount_transit = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    checks_count_transit = db.Column(db.Integer, server_default=db.FetchedValue())
    checks_amount_transit = db.Column(db.Double(53), server_default=db.FetchedValue())
    movil_payment_received_count = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    movil_payment_received_amount = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    movil_payment_made_count = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    movil_payment_made_amount = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )

    bank_account1 = db.relationship(
        "BankAccount",
        primaryjoin="BankConciliation.bank_account == BankAccount.code",
        backref="bank_conciliations",
    )


class BankTransactionAccountDetail(db.Model):
    __tablename__ = "bank_transaction_account_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.bank_transactions.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    line = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    account_accounting = db.Column(
        db.ForeignKey(
            "public.account_accounting.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    credit = db.Column(db.Double(53))
    debit = db.Column(db.Double(53))

    account_accounting1 = db.relationship(
        "AccountAccounting",
        primaryjoin="BankTransactionAccountDetail.account_accounting == AccountAccounting.code",
        backref="bank_transaction_account_details",
    )
    bank_transaction = db.relationship(
        "BankTransaction",
        primaryjoin="BankTransactionAccountDetail.main_correlative == BankTransaction.correlative",
        backref="bank_transaction_account_details",
    )


class BankTransaction(db.Model):
    __tablename__ = "bank_transactions"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    bank_account = db.Column(
        db.ForeignKey(
            "public.bank_account.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    operation_type = db.Column(db.String)
    reference_number = db.Column(db.String)
    description = db.Column(db.String)
    operation_comments = db.Column(db.String)
    amount = db.Column(db.Double(53))
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    credit = db.Column(db.Double(53))
    debit = db.Column(db.Double(53))
    beneficiary = db.Column(
        db.ForeignKey(
            "public.beneficiaries.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    endosable = db.Column(db.Boolean, server_default=db.FetchedValue())
    amount_other_bank = db.Column(db.Double(53))
    amount_same_bank = db.Column(db.Double(53))
    release_date_other_bank = db.Column(db.Date)
    release_date_same_bank = db.Column(db.Date)
    bank_account_related = db.Column(
        db.ForeignKey(
            "public.bank_account.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    cash = db.Column(db.Double(53))
    deferred_same_bank = db.Column(db.Boolean, server_default=db.FetchedValue())
    deferred_other_bank = db.Column(db.Boolean, server_default=db.FetchedValue())
    ready_to_conciliate = db.Column(db.Boolean, server_default=db.FetchedValue())
    correlative_conciliation = db.Column(
        db.Integer, nullable=False, server_default=db.FetchedValue()
    )
    beneficiary_description = db.Column(db.String)
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    bank_related = db.Column(db.String, server_default=db.FetchedValue())

    bank_account1 = db.relationship(
        "BankAccount",
        primaryjoin="BankTransaction.bank_account == BankAccount.code",
        backref="bankaccount_bank_transactions",
    )
    bank_account2 = db.relationship(
        "BankAccount",
        primaryjoin="BankTransaction.bank_account_related == BankAccount.code",
        backref="bankaccount_bank_transactions_0",
    )
    beneficiary1 = db.relationship(
        "Beneficiary",
        primaryjoin="BankTransaction.beneficiary == Beneficiary.code",
        backref="bank_transactions",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="BankTransaction.station == Station.code",
        backref="bank_transactions",
    )
    user = db.relationship(
        "User",
        primaryjoin="BankTransaction.user_code == User.code",
        backref="bank_transactions",
    )
    parents = db.relationship(
        "BankTransaction",
        secondary="bank_transactions_rel",
        primaryjoin="BankTransaction.correlative == bank_transactions_rel.c.correlative",
        secondaryjoin="BankTransaction.correlative == bank_transactions_rel.c.correlative_rel",
        backref="bank_transactions",
    )


t_bank_transactions_rel = db.Table(
    "bank_transactions_rel",
    db.Column(
        "correlative",
        db.ForeignKey(
            "public.bank_transactions.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    ),
    db.Column(
        "correlative_rel",
        db.ForeignKey(
            "public.bank_transactions.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    ),
)


class Bank(db.Model):
    __tablename__ = "banks"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    days_deferred_same_bank = db.Column(db.Integer, server_default=db.FetchedValue())
    days_deferred_other_bank = db.Column(db.Integer, server_default=db.FetchedValue())


class Beneficiary(db.Model):
    __tablename__ = "beneficiaries"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    description = db.Column(db.String)


class Bot(db.Model):
    __tablename__ = "bot"
    __table_args__ = {"schema": "public", "extend_existing": True}

    token = db.Column(db.String, primary_key=True)


class BotUser(db.Model):
    __tablename__ = "bot_users"
    __table_args__ = {"schema": "public", "extend_existing": True}

    chat_id = db.Column(db.BigInteger, primary_key=True)
    enabled = db.Column(db.Boolean, server_default=db.FetchedValue())
    account = db.Column(db.String, server_default=db.FetchedValue())
    user_code = db.Column(db.String, server_default=db.FetchedValue())


class Browser(db.Model):
    __tablename__ = "browser"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    query = db.Column(db.String)
    internal_search_field = db.Column(db.Integer)
    show_field = db.Column(db.Integer)
    full_screen = db.Column(db.Boolean)
    resizable = db.Column(db.Boolean)
    lenght = db.Column(db.Integer)
    width = db.Column(db.Integer)
    show_coin = db.Column(db.Boolean, server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    paginate = db.Column(db.Boolean, server_default=db.FetchedValue())
    query_count = db.Column(db.String, server_default=db.FetchedValue())
    max_rows_by_page = db.Column(db.Integer, server_default=db.FetchedValue())
    font_size = db.Column(db.Integer, server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin", primaryjoin="Browser.coin_code == Coin.code", backref="browsers"
    )


class BrowserColumn(db.Model):
    __tablename__ = "browser_columns"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey("public.browser.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    field = db.Column(db.String, primary_key=True, nullable=False)
    field_label = db.Column(db.String)
    width = db.Column(db.Integer)
    visible = db.Column(db.Boolean)
    index_column = db.Column(db.Integer)
    column_type = db.Column(db.String, server_default=db.FetchedValue())
    column_symbol = db.Column(db.Boolean, server_default=db.FetchedValue())
    use_symbol = db.Column(db.Boolean, server_default=db.FetchedValue())

    browser = db.relationship(
        "Browser",
        primaryjoin="BrowserColumn.main_code == Browser.code",
        backref="browser_columns",
    )


class BrowserFilter(db.Model):
    __tablename__ = "browser_filters"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey("public.browser.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    field = db.Column(db.String, primary_key=True, nullable=False)
    field_label = db.Column(db.String)
    index_column = db.Column(db.Integer)
    index_order = db.Column(db.Integer)
    table_name = db.Column(db.String, server_default=db.FetchedValue())

    browser = db.relationship(
        "Browser",
        primaryjoin="BrowserFilter.main_code == Browser.code",
        backref="browser_filters",
    )


class BrowserParameter(db.Model):
    __tablename__ = "browser_parameters"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey("public.browser.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    default_value = db.Column(db.String)
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )

    browser = db.relationship(
        "Browser",
        primaryjoin="BrowserParameter.main_code == Browser.code",
        backref="browser_parameters",
    )


class CardType(db.Model):
    __tablename__ = "card_types"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    card_type = db.Column(db.String)


class CashOperation(db.Model):
    __tablename__ = "cash_operation"
    __table_args__ = {"schema": "public", "extend_existing": True}

    id = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    emission_date = db.Column(db.Date)
    document_no = db.Column(db.String)
    operation_type = db.Column(db.String)
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    station_code = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    description = db.Column(db.String)
    operation_comments = db.Column(db.String)

    station = db.relationship(
        "Station",
        primaryjoin="CashOperation.station_code == Station.code",
        backref="cash_operations",
    )
    user = db.relationship(
        "User",
        primaryjoin="CashOperation.user_code == User.code",
        backref="cash_operations",
    )


class City(db.Model):
    __tablename__ = "citys"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class ClientGroup(db.Model):
    __tablename__ = "client_groups"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class Client(db.Model):
    __tablename__ = "clients"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    address = db.Column(db.String)
    client_id = db.Column(db.String)
    email = db.Column(db.String)
    phone = db.Column(db.String)
    contact = db.Column(db.String)
    country = db.Column(
        db.ForeignKey("public.countrys.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    province = db.Column(
        db.ForeignKey("public.provinces.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    city = db.Column(
        db.ForeignKey("public.citys.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    town = db.Column(
        db.ForeignKey("public.towns.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    area_sales = db.Column(
        db.ForeignKey("public.area_sales.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    seller = db.Column(
        db.ForeignKey("public.sellers.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    client_group = db.Column(
        db.ForeignKey(
            "public.client_groups.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    credit_days = db.Column(db.Integer)
    credit_limit = db.Column(db.Double(53))
    discount = db.Column(db.Double(53))
    client_type = db.Column(
        db.ForeignKey(
            "public.person_type.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    sale_price = db.Column(db.Integer)
    status = db.Column(db.String)
    name_fiscal = db.Column(db.Integer)
    generic_client = db.Column(db.Boolean)
    cond_property_type = db.Column(
        db.ForeignKey(
            "public.cond_property_type.code", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        server_default=db.FetchedValue(),
    )
    cond_floor = db.Column(
        db.ForeignKey(
            "public.cond_floor.code", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        server_default=db.FetchedValue(),
    )
    cond_aliquot = db.Column(db.Double(53), server_default=db.FetchedValue())
    cond_surface = db.Column(db.Double(53), server_default=db.FetchedValue())
    client_classification = db.Column(db.String, server_default=db.FetchedValue())
    allow_expired_balance = db.Column(db.Boolean, server_default=db.FetchedValue())
    retention_tax_agent = db.Column(db.Boolean, server_default=db.FetchedValue())
    retention_municipal_agent = db.Column(db.Boolean, server_default=db.FetchedValue())
    retention_islr_agent = db.Column(db.Boolean, server_default=db.FetchedValue())

    area_sale = db.relationship(
        "AreaSale", primaryjoin="Client.area_sales == AreaSale.code", backref="clients"
    )
    city1 = db.relationship(
        "City", primaryjoin="Client.city == City.code", backref="clients"
    )
    client_group1 = db.relationship(
        "ClientGroup",
        primaryjoin="Client.client_group == ClientGroup.code",
        backref="clients",
    )
    person_type = db.relationship(
        "PersonType",
        primaryjoin="Client.client_type == PersonType.code",
        backref="persontype_clients",
    )
    person_type1 = db.relationship(
        "PersonType",
        primaryjoin="Client.client_type == PersonType.code",
        backref=db.backref(
            "persontype_clients_0", overlaps="person_type,persontype_clients"
        ),
        overlaps="person_type,persontype_clients",
    )
    cond_floor1 = db.relationship(
        "CondFloor",
        primaryjoin="Client.cond_floor == CondFloor.code",
        backref="clients",
    )
    cond_property_type1 = db.relationship(
        "CondPropertyType",
        primaryjoin="Client.cond_property_type == CondPropertyType.code",
        backref="clients",
    )
    country1 = db.relationship(
        "Country", primaryjoin="Client.country == Country.code", backref="clients"
    )
    province1 = db.relationship(
        "Province", primaryjoin="Client.province == Province.code", backref="clients"
    )
    seller1 = db.relationship(
        "Seller", primaryjoin="Client.seller == Seller.code", backref="clients"
    )
    town1 = db.relationship(
        "Town", primaryjoin="Client.town == Town.code", backref="clients"
    )


class ClientsAddres(db.Model):
    __tablename__ = "clients_address"
    __table_args__ = {"schema": "public", "extend_existing": True}

    client_code = db.Column(
        db.ForeignKey("public.clients.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    index_order = db.Column(db.Integer, primary_key=True, nullable=False)
    address = db.Column(db.String)
    contact = db.Column(db.String)
    phone = db.Column(db.String)
    default_address = db.Column(db.Boolean, server_default=db.FetchedValue())

    client = db.relationship(
        "Client",
        primaryjoin="ClientsAddres.client_code == Client.code",
        backref="clients_address",
    )


class ClientsBalance(db.Model):
    __tablename__ = "clients_balance"
    __table_args__ = {"schema": "public", "extend_existing": True}

    client = db.Column(
        db.ForeignKey("public.clients.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    emission_date = db.Column(db.Date, primary_key=True, nullable=False)
    initial_balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    credits = db.Column(db.Double(53), server_default=db.FetchedValue())
    debits = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())

    client1 = db.relationship(
        "Client",
        primaryjoin="ClientsBalance.client == Client.code",
        backref="clients_balances",
    )


class ClosingSalesPoint(db.Model):
    __tablename__ = "closing_sales_point"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    document_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    sale_point = db.Column(
        db.ForeignKey(
            "public.sale_points.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    bank_account = db.Column(
        db.ForeignKey(
            "public.bank_account.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    lot = db.Column(db.String)
    emission_date_sale_point = db.Column(db.Date)
    date_bank_credit = db.Column(db.Date)
    total = db.Column(db.Double(53))
    total_commission = db.Column(db.Double(53))
    total_above_commission = db.Column(db.Double(53))
    total_credit_bank = db.Column(db.Double(53))
    total_islr = db.Column(db.Double(53), server_default=db.FetchedValue())

    bank_account1 = db.relationship(
        "BankAccount",
        primaryjoin="ClosingSalesPoint.bank_account == BankAccount.code",
        backref="closing_sales_points",
    )
    sale_point1 = db.relationship(
        "SalePoint",
        primaryjoin="ClosingSalesPoint.sale_point == SalePoint.code",
        backref="closing_sales_points",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="ClosingSalesPoint.station == Station.code",
        backref="closing_sales_points",
    )
    user = db.relationship(
        "User",
        primaryjoin="ClosingSalesPoint.user_code == User.code",
        backref="closing_sales_points",
    )


class ClosingSalesPointBank(db.Model):
    __tablename__ = "closing_sales_point_bank"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.closing_sales_point.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    bank_correlative = db.Column(db.Integer, primary_key=True, nullable=False)

    closing_sales_point = db.relationship(
        "ClosingSalesPoint",
        primaryjoin="ClosingSalesPointBank.main_correlative == ClosingSalesPoint.correlative",
        backref="closing_sales_point_banks",
    )


class ClosingSalesPointCard(db.Model):
    __tablename__ = "closing_sales_point_card"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.closing_sales_point.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    card_type = db.Column(
        db.ForeignKey("public.card_types.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    total_details = db.Column(db.Double(53))
    total_sales_point = db.Column(db.Double(53))
    percent_commission = db.Column(db.Double(53))
    commission = db.Column(db.Double(53))
    percent_above_commission = db.Column(db.Double(53))
    commission_above_commission = db.Column(db.Double(53))
    total_credit_bank = db.Column(db.Double(53))
    percent_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    commission_islr = db.Column(db.Double(53), server_default=db.FetchedValue())

    card_type1 = db.relationship(
        "CardType",
        primaryjoin="ClosingSalesPointCard.card_type == CardType.code",
        backref="closing_sales_point_cards",
    )
    closing_sales_point = db.relationship(
        "ClosingSalesPoint",
        primaryjoin="ClosingSalesPointCard.main_correlative == ClosingSalesPoint.correlative",
        backref="closing_sales_point_cards",
    )


t_closing_sales_point_way_to_pay = db.Table(
    "closing_sales_point_way_to_pay",
    db.Column(
        "main_correlative",
        db.ForeignKey(
            "public.closing_sales_point.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    ),
    db.Column(
        "line_way_to_pay_detail",
        db.ForeignKey(
            "public.way_to_pay_details.line", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    ),
)


class CodesIslr(db.Model):
    __tablename__ = "codes_islr"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    legalbase1808 = db.Column(db.String)
    percenttaxablenaturalresident = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percenttaxablenaturalnoresident = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percentretentionnaturalresident = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percentretentionnaturalnoresident = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    applytohigherpaymentnaturalresident = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    applytohigherpaymentnaturalnoresident = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    sustraendonaturalresidente = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    codenaturalresidente = db.Column(db.String)
    codenaturalnoresidente = db.Column(db.String)
    percenttaxablejuridicaldomiciled = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percenttaxablejuridicalnodomiciled = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percentretentionjuridicaldomiciled = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percentretentionjuridicalnodomiciled = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    applytohigherpaymentjuridicaldomiciled = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    applytohigherpaymentjuridicalnodomiciled = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    codejuridicaldomiciled = db.Column(db.String)
    codejuridicalnodomiciled = db.Column(db.String)


class Coin(db.Model):
    __tablename__ = "coin"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    symbol = db.Column(db.String)
    sales_aliquot = db.Column(db.Double(53))
    buy_aliquot = db.Column(db.Double(53))
    factor_type = db.Column(db.Integer, server_default=db.FetchedValue())
    rounding_type = db.Column(db.Integer)
    status = db.Column(db.String, server_default=db.FetchedValue())
    show_in_browsers = db.Column(
        db.Boolean, nullable=False, server_default=db.FetchedValue()
    )
    value_inventory = db.Column(
        db.Boolean, nullable=False, server_default=db.FetchedValue()
    )
    apply_igtf = db.Column(db.Boolean, server_default=db.FetchedValue())


class CoinHistory(db.Model):
    __tablename__ = "coin_history"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    main_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="CASCADE", onupdate="CASCADE")
    )
    sales_aliquot = db.Column(db.Double(53))
    buy_aliquot = db.Column(db.Double(53))
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    coin = db.relationship(
        "Coin",
        primaryjoin="CoinHistory.main_code == Coin.code",
        backref="coin_histories",
    )
    user = db.relationship(
        "User",
        primaryjoin="CoinHistory.user_code == User.code",
        backref="coin_histories",
    )


class Color(db.Model):
    __tablename__ = "colors"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class Command(db.Model):
    __tablename__ = "command"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    department = db.Column(
        db.ForeignKey("public.department.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    printer = db.Column(db.String)
    display_format = db.Column(db.Integer, server_default=db.FetchedValue())

    department1 = db.relationship(
        "Department",
        primaryjoin="Command.department == Department.code",
        backref="commands",
    )


class Company(db.Model):
    __tablename__ = "company"
    __table_args__ = {"schema": "public", "extend_existing": True}

    id = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    address = db.Column(db.String)
    phone = db.Column(db.String)
    logo = db.Column(db.LargeBinary)
    logo_type = db.Column(db.String)
    email = db.Column(
        db.ForeignKey("public.emails.account", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    contact = db.Column(db.String)
    key_activation = db.Column(db.LargeBinary)
    serial_no = db.Column(db.String)
    restorant_image = db.Column(db.LargeBinary)
    restorant_image_type = db.Column(db.String)
    main_image = db.Column(db.LargeBinary)
    main_image_type = db.Column(db.String)
    field_1 = db.Column(db.String)
    field_2 = db.Column(db.String)
    field_3 = db.Column(db.String)
    field_4 = db.Column(db.String)
    field_5 = db.Column(db.String)
    field_6 = db.Column(db.String)
    field_7 = db.Column(db.String)
    field_8 = db.Column(db.String)
    field_9 = db.Column(db.String)
    field_10 = db.Column(db.String)
    field_11 = db.Column(db.String)
    field_12 = db.Column(db.String)
    field_13 = db.Column(db.String)
    field_14 = db.Column(db.String, server_default=db.FetchedValue())
    field_15 = db.Column(db.String)
    field_16 = db.Column(db.String)
    field_17 = db.Column(db.String)
    field_18 = db.Column(db.String)
    field_19 = db.Column(db.String)
    field_20 = db.Column(db.String)
    field_21 = db.Column(db.String)
    field_22 = db.Column(db.String)
    field_23 = db.Column(db.String)
    field_24 = db.Column(db.String)
    field_25 = db.Column(db.String)
    field_26 = db.Column(db.String)
    field_27 = db.Column(db.String)
    field_28 = db.Column(db.String)
    field_29 = db.Column(db.String)
    field_30 = db.Column(db.String)
    field_31 = db.Column(db.String)

    email1 = db.relationship(
        "Email", primaryjoin="Company.email == Email.account", backref="companies"
    )


class CondAdditionalShare(db.Model):
    __tablename__ = "cond_additional_share"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    document_no = db.Column(db.String)
    description = db.Column(db.String)
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    total = db.Column(db.Double(53))
    share_no = db.Column(db.Double(53))
    total_share = db.Column(db.Double(53))

    station1 = db.relationship(
        "Station",
        primaryjoin="CondAdditionalShare.station == Station.code",
        backref="cond_additional_shares",
    )
    user = db.relationship(
        "User",
        primaryjoin="CondAdditionalShare.user_code == User.code",
        backref="cond_additional_shares",
    )


class CondAdditionalShareCoin(db.Model):
    __tablename__ = "cond_additional_share_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.cond_additional_share.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    factor_type = db.Column(db.Integer)
    factor_aliquot = db.Column(db.Double(53))
    total = db.Column(db.Double(53))
    total_share = db.Column(db.Double(53))

    coin = db.relationship(
        "Coin",
        primaryjoin="CondAdditionalShareCoin.coin_code == Coin.code",
        backref="cond_additional_share_coins",
    )
    cond_additional_share = db.relationship(
        "CondAdditionalShare",
        primaryjoin="CondAdditionalShareCoin.main_correlative == CondAdditionalShare.correlative",
        backref="cond_additional_share_coins",
    )


class CondAdditionalShareDetail(db.Model):
    __tablename__ = "cond_additional_share_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.cond_additional_share.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    correlative_receivable = db.Column(db.Integer)

    cond_additional_share = db.relationship(
        "CondAdditionalShare",
        primaryjoin="CondAdditionalShareDetail.main_correlative == CondAdditionalShare.correlative",
        backref="cond_additional_share_details",
    )


class CondClosureExpConcept(db.Model):
    __tablename__ = "cond_closure_exp_concept"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.cond_closure_expense.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        unique=True,
        server_default=db.FetchedValue(),
    )
    concept_code = db.Column(
        db.ForeignKey(
            "public.cond_concept.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    concept_description = db.Column(db.String)
    total_detail = db.Column(db.Double(53))
    total = db.Column(db.Double(53))

    cond_concept = db.relationship(
        "CondConcept",
        primaryjoin="CondClosureExpConcept.concept_code == CondConcept.code",
        backref="cond_closure_exp_concepts",
    )
    cond_closure_expense = db.relationship(
        "CondClosureExpense",
        primaryjoin="CondClosureExpConcept.main_correlative == CondClosureExpense.correlative",
        backref="cond_closure_exp_concepts",
    )


class CondClosureExpConceptCoin(db.Model):
    __tablename__ = "cond_closure_exp_concept_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.cond_closure_exp_concept.main_correlative",
                "public.cond_closure_exp_concept.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    total_detail = db.Column(db.Double(53))
    total = db.Column(db.Double(53))

    coin = db.relationship(
        "Coin",
        primaryjoin="CondClosureExpConceptCoin.coin_code == Coin.code",
        backref="cond_closure_exp_concept_coins",
    )
    cond_closure_exp_concept = db.relationship(
        "CondClosureExpConcept",
        primaryjoin="and_(CondClosureExpConceptCoin.main_correlative == CondClosureExpConcept.main_correlative, CondClosureExpConceptCoin.main_line == CondClosureExpConcept.line)",
        backref="cond_closure_exp_concept_coins",
    )


class CondClosureExpDetail(db.Model):
    __tablename__ = "cond_closure_exp_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.cond_closure_expense.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_rel = db.Column(db.Integer, primary_key=True, nullable=False)
    module_rel = db.Column(db.String, primary_key=True, nullable=False)

    cond_closure_expense = db.relationship(
        "CondClosureExpense",
        primaryjoin="CondClosureExpDetail.main_correlative == CondClosureExpense.correlative",
        backref="cond_closure_exp_details",
    )


class CondClosureExpense(db.Model):
    __tablename__ = "cond_closure_expense"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    emission_date = db.Column(db.Date)
    exp_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    period = db.Column(db.String)
    description = db.Column(db.String)
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    total_expense = db.Column(db.Double(53))
    total_income = db.Column(db.Double(53))
    total_prevision = db.Column(db.Double(53))
    total = db.Column(db.Double(53))
    register_hour = db.Column(db.Time)

    station1 = db.relationship(
        "Station",
        primaryjoin="CondClosureExpense.station == Station.code",
        backref="cond_closure_expenses",
    )
    user = db.relationship(
        "User",
        primaryjoin="CondClosureExpense.user_code == User.code",
        backref="cond_closure_expenses",
    )


class CondClosureExpenseCoin(db.Model):
    __tablename__ = "cond_closure_expense_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.cond_closure_expense.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    factor_type = db.Column(db.Integer)
    factor_aliquot = db.Column(db.Double(53))
    total_expense = db.Column(db.Double(53))
    total_income = db.Column(db.Double(53))
    total_prevision = db.Column(db.Double(53))
    total = db.Column(db.Double(53))

    coin = db.relationship(
        "Coin",
        primaryjoin="CondClosureExpenseCoin.coin_code == Coin.code",
        backref="cond_closure_expense_coins",
    )
    cond_closure_expense = db.relationship(
        "CondClosureExpense",
        primaryjoin="CondClosureExpenseCoin.main_correlative == CondClosureExpense.correlative",
        backref="cond_closure_expense_coins",
    )


class CondConcept(db.Model):
    __tablename__ = "cond_concept"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    apply_to_prevision = db.Column(db.Boolean, server_default=db.FetchedValue())
    fixed_value = db.Column(db.Boolean, server_default=db.FetchedValue())
    ordinary_expense = db.Column(db.Boolean, server_default=db.FetchedValue())
    individual_expense = db.Column(db.Boolean, server_default=db.FetchedValue())
    prevision = db.Column(db.Boolean, server_default=db.FetchedValue())
    is_percent = db.Column(db.Boolean, server_default=db.FetchedValue())
    amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    formula = db.Column(db.String, server_default=db.FetchedValue())
    edit_name = db.Column(db.Boolean, server_default=db.FetchedValue())
    status = db.Column(
        db.ForeignKey("public.status.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    allow_edit_value = db.Column(db.Boolean, server_default=db.FetchedValue())
    show_if_cero = db.Column(db.Boolean, server_default=db.FetchedValue())
    calc_order = db.Column(db.Integer, server_default=db.FetchedValue())
    concept_type = db.Column(db.Integer, server_default=db.FetchedValue())

    status1 = db.relationship(
        "Status",
        primaryjoin="CondConcept.status == Status.code",
        backref="cond_concepts",
    )


class CondCondominium(db.Model):
    __tablename__ = "cond_condominium"
    __table_args__ = {"schema": "public", "extend_existing": True}

    id_condominium = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    address = db.Column(db.String)
    phone = db.Column(db.String)
    period = db.Column(db.String)
    factor_aliquot = db.Column(db.Double(53), server_default=db.FetchedValue())


class CondFloor(db.Model):
    __tablename__ = "cond_floor"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class CondPropertyType(db.Model):
    __tablename__ = "cond_property_type"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class CondReceipt(db.Model):
    __tablename__ = "cond_receipt"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    correlative_rel = db.Column(
        db.ForeignKey(
            "public.cond_closure_expense.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    emission_date = db.Column(db.Date)
    exp_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    document_no = db.Column(db.String)
    description = db.Column(db.String)
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    property_code = db.Column(
        db.ForeignKey("public.clients.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    property_description = db.Column(db.String)
    property_id = db.Column(db.String)
    property_address = db.Column(db.String)
    property_phone = db.Column(db.String)
    aliquot = db.Column(db.Double(53))
    balance = db.Column(db.Double(53))
    total_expense = db.Column(db.Double(53))
    total_income = db.Column(db.Double(53))
    total_prevision = db.Column(db.Double(53))
    total = db.Column(db.Double(53))
    total_individual_exp = db.Column(db.Double(53))
    total_operation = db.Column(db.Double(53))
    correlative_receivable = db.Column(
        db.ForeignKey(
            "public.receivable.correlative", ondelete="CASCADE", onupdate="CASCADE"
        )
    )
    balance_indexing = db.Column(db.Double(53), server_default=db.FetchedValue())

    receivable = db.relationship(
        "Receivable",
        primaryjoin="CondReceipt.correlative_receivable == Receivable.correlative",
        backref="cond_receipts",
    )
    cond_closure_expense = db.relationship(
        "CondClosureExpense",
        primaryjoin="CondReceipt.correlative_rel == CondClosureExpense.correlative",
        backref="cond_receipts",
    )
    client = db.relationship(
        "Client",
        primaryjoin="CondReceipt.property_code == Client.code",
        backref="cond_receipts",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="CondReceipt.station == Station.code",
        backref="cond_receipts",
    )
    user = db.relationship(
        "User",
        primaryjoin="CondReceipt.user_code == User.code",
        backref="cond_receipts",
    )


class CondReceiptCoin(db.Model):
    __tablename__ = "cond_receipt_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.cond_receipt.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_rel = db.Column(db.Integer)
    coin_code = db.Column(db.String, primary_key=True, nullable=False)
    total_expense = db.Column(db.Double(53))
    total_income = db.Column(db.Double(53))
    total_prevision = db.Column(db.Double(53))
    total = db.Column(db.Double(53))
    total_individual_exp = db.Column(db.Double(53))
    total_operation = db.Column(db.Double(53))

    cond_receipt = db.relationship(
        "CondReceipt",
        primaryjoin="CondReceiptCoin.main_correlative == CondReceipt.correlative",
        backref="cond_receipt_coins",
    )


class CondReceiptConcept(db.Model):
    __tablename__ = "cond_receipt_concept"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.cond_receipt.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        nullable=False,
    )
    main_line = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Double(53))
    line = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    concept_code = db.Column(db.String)
    concept_description = db.Column(db.String)

    cond_receipt = db.relationship(
        "CondReceipt",
        primaryjoin="CondReceiptConcept.main_correlative == CondReceipt.correlative",
        backref="cond_receipt_concepts",
    )


class CondReceiptConceptCoin(db.Model):
    __tablename__ = "cond_receipt_concept_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "coin_code"],
            [
                "public.cond_receipt_coins.main_correlative",
                "public.cond_receipt_coins.coin_code",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, nullable=False)
    main_closure_concept_line = db.Column(db.Integer, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    coin_code = db.Column(db.String, primary_key=True, nullable=False)
    total = db.Column(db.Double(53))

    cond_receipt_coin = db.relationship(
        "CondReceiptCoin",
        primaryjoin="and_(CondReceiptConceptCoin.main_correlative == CondReceiptCoin.main_correlative, CondReceiptConceptCoin.coin_code == CondReceiptCoin.coin_code)",
        backref="cond_receipt_concept_coins",
    )


t_cond_receipt_details = db.Table(
    "cond_receipt_details",
    db.Column(
        "main_correlative",
        db.ForeignKey(
            "public.cond_receipt.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    ),
    db.Column(
        "correlative_rel",
        db.ForeignKey(
            "public.shopping_operation.correlative",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    ),
)


class Country(db.Model):
    __tablename__ = "countrys"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class Debtstopay(db.Model):
    __tablename__ = "debtstopay"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    operation_type = db.Column(db.String)
    document_no = db.Column(db.String)
    control_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time(True))
    provider_code = db.Column(
        db.ForeignKey("public.provider.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    provider_name = db.Column(db.String)
    provider_id = db.Column(db.String)
    provider_address = db.Column(db.String)
    provider_phone = db.Column(db.String)
    credit_days = db.Column(db.Integer)
    expiration_date = db.Column(db.Date)
    description = db.Column(db.String)
    operation_comments = db.Column(db.String)
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    debit = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_municipal = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_aditional = db.Column(db.Double(53), server_default=db.FetchedValue())
    payment_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    advance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    begin_used = db.Column(db.Boolean, server_default=db.FetchedValue())
    repayment_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    reception_date = db.Column(db.Date)
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    indexing_factor = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing_debit = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing_credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing = db.Column(db.Boolean, server_default=db.FetchedValue())
    debit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing_coin = db.Column(db.String, server_default=db.FetchedValue())
    indexing_correlative_origin = db.Column(
        db.Integer, server_default=db.FetchedValue()
    )
    indexing_module_origin = db.Column(db.String, server_default=db.FetchedValue())
    indexing_register_factor_rel = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    total_exempt = db.Column(db.Double(53), server_default=db.FetchedValue())
    canceled = db.Column(db.Boolean, server_default=db.FetchedValue())
    base_igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    igtf = db.Column(db.Double(53), server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin", primaryjoin="Debtstopay.coin_code == Coin.code", backref="debtstopays"
    )
    provider = db.relationship(
        "Provider",
        primaryjoin="Debtstopay.provider_code == Provider.code",
        backref="debtstopays",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="Debtstopay.station == Station.code",
        backref="debtstopays",
    )
    user = db.relationship(
        "User", primaryjoin="Debtstopay.user_code == User.code", backref="debtstopays"
    )


class DebtstopayReturnedCheck(db.Model):
    __tablename__ = "debtstopay_returned_check"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.debtstopay.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
    )
    check_date = db.Column(db.Date)
    check_number = db.Column(db.String)
    bank = db.Column(
        db.ForeignKey("public.banks.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    bank1 = db.relationship(
        "Bank",
        primaryjoin="DebtstopayReturnedCheck.bank == Bank.code",
        backref="debtstopay_returned_checks",
    )


class DebtstopayCoin(db.Model):
    __tablename__ = "debtstopay_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.debtstopay.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    factor_type = db.Column(db.Integer)
    factor_aliquot = db.Column(db.Double(53))
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    debit = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_municipal = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_aditional = db.Column(db.Double(53), server_default=db.FetchedValue())
    payment_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    advance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    repayment_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing_debit = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing_credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    debit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_exempt = db.Column(db.Double(53), server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin",
        primaryjoin="DebtstopayCoin.coin_code == Coin.code",
        backref="debtstopay_coins",
    )
    debtstopay = db.relationship(
        "Debtstopay",
        primaryjoin="DebtstopayCoin.main_correlative == Debtstopay.correlative",
        backref="debtstopay_coins",
    )


class DebtstopayDetail(db.Model):
    __tablename__ = "debtstopay_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.debtstopay.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_related = db.Column(
        db.ForeignKey(
            "public.debtstopay.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(db.Integer, nullable=False, server_default=db.FetchedValue())
    module_related = db.Column(db.String)
    balance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_municipal = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_note = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    relation_type = db.Column(
        db.String, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )

    debtstopay = db.relationship(
        "Debtstopay",
        primaryjoin="DebtstopayDetail.correlative_related == Debtstopay.correlative",
        backref="debtstopay_debtstopay_details",
    )
    debtstopay1 = db.relationship(
        "Debtstopay",
        primaryjoin="DebtstopayDetail.main_correlative == Debtstopay.correlative",
        backref="debtstopay_debtstopay_details_0",
    )


class DebtstopayDetailsCoin(db.Model):
    __tablename__ = "debtstopay_details_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.debtstopay.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_related = db.Column(
        db.ForeignKey(
            "public.debtstopay.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    main_line = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String)
    coin_code = db.Column(db.String, primary_key=True, nullable=False)
    balance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax = db.Column(db.Double(53))
    retention_islr = db.Column(db.Double(53))
    retention_municipal = db.Column(db.Double(53))
    credit_note = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())

    debtstopay = db.relationship(
        "Debtstopay",
        primaryjoin="DebtstopayDetailsCoin.correlative_related == Debtstopay.correlative",
        backref="debtstopay_debtstopay_details_coins",
    )
    debtstopay1 = db.relationship(
        "Debtstopay",
        primaryjoin="DebtstopayDetailsCoin.main_correlative == Debtstopay.correlative",
        backref="debtstopay_debtstopay_details_coins_0",
    )


class DebtstopayTax(db.Model):
    __tablename__ = "debtstopay_taxes"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.debtstopay.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    taxe_code = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    aliquot = db.Column(db.Double(53))
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    line = db.Column(db.Integer, nullable=False, server_default=db.FetchedValue())
    tax_type = db.Column(
        db.ForeignKey("public.tax_types.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    debtstopay = db.relationship(
        "Debtstopay",
        primaryjoin="DebtstopayTax.main_correlative == Debtstopay.correlative",
        backref="debtstopay_taxes",
    )
    tax_type1 = db.relationship(
        "TaxType",
        primaryjoin="DebtstopayTax.tax_type == TaxType.code",
        backref="debtstopay_taxes",
    )
    tax1 = db.relationship(
        "Tax",
        primaryjoin="DebtstopayTax.taxe_code == Tax.code",
        backref="debtstopay_taxes",
    )


class DebtstopayTaxesCoin(db.Model):
    __tablename__ = "debtstopay_taxes_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_taxe_code"],
            [
                "public.debtstopay_taxes.main_correlative",
                "public.debtstopay_taxes.taxe_code",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_taxe_code = db.Column(db.String, primary_key=True, nullable=False)
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    main_line = db.Column(db.Integer)

    coin = db.relationship(
        "Coin",
        primaryjoin="DebtstopayTaxesCoin.coin_code == Coin.code",
        backref="debtstopay_taxes_coins",
    )
    debtstopay_tax = db.relationship(
        "DebtstopayTax",
        primaryjoin="and_(DebtstopayTaxesCoin.main_correlative == DebtstopayTax.main_correlative, DebtstopayTaxesCoin.main_taxe_code == DebtstopayTax.taxe_code)",
        backref="debtstopay_taxes_coins",
    )


class DeliveryOperation(db.Model):
    __tablename__ = "delivery_operations"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    operation_type = db.Column(db.String)
    document_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    description = db.Column(db.String)
    operation_comments = db.Column(db.String)
    register_hour = db.Column(db.Time)
    register_date = db.Column(db.Date)
    driver = db.Column(
        db.ForeignKey("public.drivers.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    vehicle = db.Column(
        db.ForeignKey("public.vehicles.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    total_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_weight = db.Column(db.Double(53), server_default=db.FetchedValue())
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    pending = db.Column(db.Boolean)
    canceled = db.Column(db.Boolean)

    driver1 = db.relationship(
        "Driver",
        primaryjoin="DeliveryOperation.driver == Driver.code",
        backref="delivery_operations",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="DeliveryOperation.station == Station.code",
        backref="delivery_operations",
    )
    user = db.relationship(
        "User",
        primaryjoin="DeliveryOperation.user_code == User.code",
        backref="delivery_operations",
    )
    vehicle1 = db.relationship(
        "Vehicle",
        primaryjoin="DeliveryOperation.vehicle == Vehicle.code",
        backref="delivery_operations",
    )


class DeliveryOperationsDetail(db.Model):
    __tablename__ = "delivery_operations_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.delivery_operations.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        unique=True,
        server_default=db.FetchedValue(),
    )
    correlative_related = db.Column(
        db.ForeignKey(
            "public.sales_operation.correlative",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        )
    )

    sales_operation = db.relationship(
        "SalesOperation",
        primaryjoin="DeliveryOperationsDetail.correlative_related == SalesOperation.correlative",
        backref="delivery_operations_details",
    )
    delivery_operation = db.relationship(
        "DeliveryOperation",
        primaryjoin="DeliveryOperationsDetail.main_correlative == DeliveryOperation.correlative",
        backref="delivery_operations_details",
    )
    parents = db.relationship(
        "DeliveryOperationsDetail",
        secondary="delivery_operations_details_load",
        primaryjoin="and_(DeliveryOperationsDetail.main_correlative == delivery_operations_details_load.c.load_correlative, DeliveryOperationsDetail.line == delivery_operations_details_load.c.load_line)",
        secondaryjoin="and_(DeliveryOperationsDetail.main_correlative == delivery_operations_details_load.c.main_correlative, DeliveryOperationsDetail.line == delivery_operations_details_load.c.main_line)",
        backref="delivery_operations_details",
    )


t_delivery_operations_details_load = db.Table(
    "delivery_operations_details_load",
    db.Column("main_correlative", db.Integer),
    db.Column("main_line", db.Integer, primary_key=True),
    db.Column("load_correlative", db.Integer),
    db.Column("load_line", db.Integer),
    db.ForeignKeyConstraint(
        ["load_correlative", "load_line"],
        [
            "public.delivery_operations_details.main_correlative",
            "public.delivery_operations_details.line",
        ],
        ondelete="RESTRICT",
        onupdate="CASCADE",
    ),
    db.ForeignKeyConstraint(
        ["main_correlative", "main_line"],
        [
            "public.delivery_operations_details.main_correlative",
            "public.delivery_operations_details.line",
        ],
        ondelete="CASCADE",
        onupdate="CASCADE",
    ),
)


class Department(db.Model):
    __tablename__ = "department"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    perc_maximum_price = db.Column(db.Double(53))
    perc_minimum_price = db.Column(db.Double(53))
    perc_offer_price = db.Column(db.Double(53))
    perc_higher_price = db.Column(db.Double(53))
    father_department = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )


class DepartmentsImage(Department):
    __tablename__ = "departments_image"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey("public.department.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    image_type = db.Column(db.String)
    department_image = db.Column(db.LargeBinary)


class RestPosDepartment(Department):
    __tablename__ = "rest_pos_department"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(
        db.ForeignKey("public.department.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    index_order = db.Column(db.Integer)


class Driver(db.Model):
    __tablename__ = "drivers"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    phone = db.Column(db.String)


class Email(db.Model):
    __tablename__ = "emails"
    __table_args__ = {"schema": "public", "extend_existing": True}

    account = db.Column(db.String, primary_key=True)
    account_password = db.Column(db.String)
    port = db.Column(db.Integer)
    server_email = db.Column(db.String)
    topic = db.Column(db.String)
    message = db.Column(db.String)
    description = db.Column(db.String)


class FiscalPrinterConfig(db.Model):
    __tablename__ = "fiscal_printer_config"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, nullable=False, unique=True, server_default=db.FetchedValue()
    )
    station_code = db.Column(db.String, primary_key=True)
    fiscal_printer = db.Column(db.String)
    fiscal_printer_port = db.Column(db.String)
    fiscal_printer_serial = db.Column(db.String)
    use_sale_point = db.Column(db.Boolean)
    use_sale = db.Column(db.Boolean)
    print_product_code = db.Column(db.Boolean)
    print_product_code_ncr = db.Column(db.Boolean)
    flag_21 = db.Column(db.String)
    print_total_coin_fc = db.Column(db.String, server_default=db.FetchedValue())
    lines_product_description = db.Column(
        db.Integer, nullable=False, server_default=db.FetchedValue()
    )
    remote = db.Column(db.Boolean, server_default=db.FetchedValue())
    flag_50 = db.Column(db.String, server_default=db.FetchedValue())
    has_connected_drawer = db.Column(db.Boolean, server_default=db.FetchedValue())


class FiscalPrinterConfigDetail(db.Model):
    __tablename__ = "fiscal_printer_config_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True, nullable=False)
    description = db.Column(db.String)
    label_field = db.Column(db.String)
    field_order = db.Column(db.Integer)
    lines_no = db.Column(db.Integer)
    operation_type = db.Column(db.String, primary_key=True, nullable=False)
    visible = db.Column(db.Boolean)
    position_field = db.Column(db.Integer)
    main_correlative = db.Column(
        db.ForeignKey(
            "public.fiscal_printer_config.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )

    fiscal_printer_config = db.relationship(
        "FiscalPrinterConfig",
        primaryjoin="FiscalPrinterConfigDetail.main_correlative == FiscalPrinterConfig.correlative",
        backref="fiscal_printer_config_details",
    )


class FiscalPrinterZ(db.Model):
    __tablename__ = "fiscal_printer_z"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    fiscal_printer_serial = db.Column(db.String)
    fiscal_printer_z = db.Column(db.String)
    z_date = db.Column(db.DateTime)
    last_invoice = db.Column(db.String)
    last_invoice_date = db.Column(db.Date)
    last_debit_note = db.Column(db.String)
    last_debit_note_date = db.Column(db.Date)
    last_credit_note = db.Column(db.String)
    last_credit_note_date = db.Column(db.Date)


class FiscalPrinterZDetail(db.Model):
    __tablename__ = "fiscal_printer_z_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.fiscal_printer_z.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    operation_type = db.Column(db.String)
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    tax_type = db.Column(db.Integer)

    fiscal_printer_z = db.relationship(
        "FiscalPrinterZ",
        primaryjoin="FiscalPrinterZDetail.main_correlative == FiscalPrinterZ.correlative",
        backref="fiscal_printer_z_details",
    )


class InventoryOperation(db.Model):
    __tablename__ = "inventory_operation"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    operation_type = db.Column(db.String)
    document_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    wait = db.Column(db.Boolean)
    description = db.Column(db.String)
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    destination_store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    destination_location = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    operation_comments = db.Column(db.String)
    begin_used = db.Column(db.Boolean, server_default=db.FetchedValue())
    register_hour = db.Column(db.Time)
    register_date = db.Column(db.Date)
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    total_details = db.Column(db.Integer, server_default=db.FetchedValue())
    total_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    internal_use = db.Column(db.Boolean, server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin",
        primaryjoin="InventoryOperation.coin_code == Coin.code",
        backref="inventory_operations",
    )
    location = db.relationship(
        "Location",
        primaryjoin="InventoryOperation.destination_location == Location.code",
        backref="location_inventory_operations",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="InventoryOperation.destination_store == Store.code",
        backref="store_inventory_operations",
    )
    location1 = db.relationship(
        "Location",
        primaryjoin="InventoryOperation.locations == Location.code",
        backref="location_inventory_operations_0",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="InventoryOperation.station == Station.code",
        backref="inventory_operations",
    )
    store2 = db.relationship(
        "Store",
        primaryjoin="InventoryOperation.store == Store.code",
        backref="store_inventory_operations_0",
    )
    user = db.relationship(
        "User",
        primaryjoin="InventoryOperation.user_code == User.code",
        backref="inventory_operations",
    )
    # Relación explícita hacia los detalles de la operación.
    # Ya existe un backref llamado 'inventory_operation_details' definido en InventoryOperationDetail,
    # este alias facilita el acceso directo desde InventoryOperation y mejora el autocompletado.
    details = db.relationship(
        "InventoryOperationDetail",
        primaryjoin="InventoryOperation.correlative == InventoryOperationDetail.main_correlative",
        lazy="selectin",
        overlaps="inventory_operation_details,inventory_operation",
    )


class InventoryOperationFlow(db.Model):
    __tablename__ = "inventory_operation_flow"
    __table_args__ = {"schema": "toolbox", "extend_existing": True}

    operation_correlative = db.Column(
        db.ForeignKey(
            "public.inventory_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    current_status = db.Column(
        db.String(25), nullable=False, server_default="RECOLLECTION_ISSUED"
    )
    recollection_issued_user = db.Column(db.String(50), nullable=False)
    recollection_issued_at = db.Column(
        db.DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    checking_user = db.Column(db.String(50))
    checked_at = db.Column(db.DateTime)
    in_transit_user = db.Column(db.String(50))
    in_transit_at = db.Column(db.DateTime)
    receiving_user = db.Column(db.String(50))
    received_at = db.Column(db.DateTime)

    inventory_operation = db.relationship(
        "InventoryOperation",
        primaryjoin="InventoryOperationFlow.operation_correlative == InventoryOperation.correlative",
        backref=db.backref("operation_flow", uselist=False),
    )


class InventoryOperationReceptionDifference(db.Model):
    __tablename__ = "inventory_operation_reception_differences"
    __table_args__ = (
        db.UniqueConstraint("operation_correlative", "detail_line"),
        {"schema": "toolbox", "extend_existing": True},
    )

    correlative = db.Column(db.Integer, primary_key=True)
    operation_correlative = db.Column(
        db.ForeignKey(
            "public.inventory_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    detail_line = db.Column(db.Integer, nullable=False)
    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    original_amount = db.Column(db.Double(53), nullable=False)
    counted_amount = db.Column(db.Double(53), nullable=False)
    difference = db.Column(db.Double(53), nullable=False)
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    detected_at = db.Column(
        db.DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = db.Column(db.DateTime)
    resolution_status = db.Column(
        db.String(20), nullable=False, server_default="PENDING"
    )
    resolution_note = db.Column(db.Text)
    resolved_user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    resolved_at = db.Column(db.DateTime)

    inventory_operation = db.relationship(
        "InventoryOperation",
        primaryjoin="InventoryOperationReceptionDifference.operation_correlative == InventoryOperation.correlative",
        backref="reception_differences",
    )
    product = db.relationship(
        "Product",
        primaryjoin="InventoryOperationReceptionDifference.product_code == Product.code",
        backref="inventory_reception_differences",
    )
    user = db.relationship(
        "User",
        primaryjoin="InventoryOperationReceptionDifference.user_code == User.code",
        backref="inventory_reception_differences",
    )
    resolved_user = db.relationship(
        "User",
        primaryjoin="InventoryOperationReceptionDifference.resolved_user_code == User.code",
        foreign_keys=[resolved_user_code],
        backref="resolved_inventory_reception_differences",
    )


class InventoryOperationCoin(db.Model):
    __tablename__ = "inventory_operation_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.inventory_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    factor_type = db.Column(db.Integer)
    buy_aliquot = db.Column(db.Double(53))
    sales_aliquot = db.Column(db.Double(53))
    way_pay_aliquot = db.Column(db.Double(53))

    coin = db.relationship(
        "Coin",
        primaryjoin="InventoryOperationCoin.coin_code == Coin.code",
        backref="inventory_operation_coins",
    )
    inventory_operation = db.relationship(
        "InventoryOperation",
        primaryjoin="InventoryOperationCoin.main_correlative == InventoryOperation.correlative",
        backref="inventory_operation_coins",
    )


class InventoryOperationDetail(db.Model):
    __tablename__ = "inventory_operation_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.inventory_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        unique=True,
        server_default=db.FetchedValue(),
    )
    code_product = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    description_product = db.Column(db.String)
    referenc = db.Column(db.String)
    mark = db.Column(db.String)
    model = db.Column(db.String)
    amount = db.Column(db.Double(53))
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    destination_store = db.Column(
        db.ForeignKey("public.store.code", ondelete="CASCADE", onupdate="CASCADE")
    )
    destination_location = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    unit = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    conversion_factor = db.Column(db.Double(53))
    unit_type = db.Column(db.Integer)
    unitary_cost = db.Column(db.Double(53))
    buy_tax = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    aliquot = db.Column(db.Double(53))
    total_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    load_by_adjustment = db.Column(db.Double(53), server_default=db.FetchedValue())
    download_by_adjustment = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    change_price = db.Column(db.Boolean, server_default=db.FetchedValue())

    tax = db.relationship(
        "Tax",
        primaryjoin="InventoryOperationDetail.buy_tax == Tax.code",
        backref="inventory_operation_details",
    )
    product = db.relationship(
        "Product",
        primaryjoin="InventoryOperationDetail.code_product == Product.code",
        backref="inventory_operation_details",
    )
    coin = db.relationship(
        "Coin",
        primaryjoin="InventoryOperationDetail.coin_code == Coin.code",
        backref="inventory_operation_details",
    )
    location = db.relationship(
        "Location",
        primaryjoin="InventoryOperationDetail.destination_location == Location.code",
        backref="location_inventory_operation_details",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="InventoryOperationDetail.destination_store == Store.code",
        backref="store_inventory_operation_details",
    )
    location1 = db.relationship(
        "Location",
        primaryjoin="InventoryOperationDetail.locations == Location.code",
        backref="location_inventory_operation_details_0",
    )
    inventory_operation = db.relationship(
        "InventoryOperation",
        primaryjoin="InventoryOperationDetail.main_correlative == InventoryOperation.correlative",
        backref="inventory_operation_details",
    )
    store2 = db.relationship(
        "Store",
        primaryjoin="InventoryOperationDetail.store == Store.code",
        backref="store_inventory_operation_details_0",
    )
    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="InventoryOperationDetail.unit == ProductsUnit.correlative",
        backref="inventory_operation_details",
    )
    failure_info = db.relationship(
        "ProductsFailure",
        primaryjoin="""and_(
            InventoryOperationDetail.code_product == foreign(ProductsFailure.product_code),
            InventoryOperationDetail.store == foreign(ProductsFailure.store_code)
        )""",
        viewonly=True,
        uselist=False,
    )


class InventoryOperationDetailsLot(InventoryOperationDetail):
    __tablename__ = "inventory_operation_details_lots"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.inventory_operation_details.main_correlative",
                "public.inventory_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    lot_number = db.Column(db.String)
    expire = db.Column(db.Boolean)
    expire_date = db.Column(db.Date)
    apply_prices = db.Column(db.Boolean)
    elaboration_date = db.Column(db.Date)
    lot_correlative = db.Column(db.Integer)


class InventoryOperationDetailsProductsUnit(db.Model):
    __tablename__ = "inventory_operation_details_products_units"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_line = db.Column(
        db.ForeignKey(
            "public.inventory_operation_details.line",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_units = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    unitary_cost = db.Column(db.Double(53))
    calculated_cost = db.Column(db.Double(53))
    average_cost = db.Column(db.Double(53))
    perc_waste_cost = db.Column(db.Double(53))
    perc_handling_cost = db.Column(db.Double(53))
    perc_operating_cost = db.Column(db.Double(53))
    perc_additional_cost = db.Column(db.Double(53))
    maximum_price = db.Column(db.Double(53))
    offer_price = db.Column(db.Double(53))
    higher_price = db.Column(db.Double(53))
    minimum_price = db.Column(db.Double(53))
    perc_maximum_price = db.Column(db.Double(53))
    perc_offer_price = db.Column(db.Double(53))
    perc_higher_price = db.Column(db.Double(53))
    perc_minimum_price = db.Column(db.Double(53))
    perc_freight_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    perc_discount_provider = db.Column(db.Double(53), server_default=db.FetchedValue())

    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="InventoryOperationDetailsProductsUnit.correlative_units == ProductsUnit.correlative",
        backref="inventory_operation_details_products_units",
    )
    inventory_operation_detail = db.relationship(
        "InventoryOperationDetail",
        primaryjoin="InventoryOperationDetailsProductsUnit.main_line == InventoryOperationDetail.line",
        backref="inventory_operation_details_products_units",
    )


class InventoryOperationDetailsSerial(db.Model):
    __tablename__ = "inventory_operation_details_serials"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.inventory_operation_details.main_correlative",
                "public.inventory_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    serial_no = db.Column(db.String)
    serial_line = db.Column(db.Integer)

    inventory_operation_detail = db.relationship(
        "InventoryOperationDetail",
        primaryjoin="and_(InventoryOperationDetailsSerial.main_correlative == InventoryOperationDetail.main_correlative, InventoryOperationDetailsSerial.main_line == InventoryOperationDetail.line)",
        backref="inventory_operation_details_serials",
    )


class InventoryOperationTax(db.Model):
    __tablename__ = "inventory_operation_taxes"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.inventory_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    taxe_code = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    aliquot = db.Column(db.Double(53))
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    tax_type = db.Column(
        db.ForeignKey("public.tax_types.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    inventory_operation = db.relationship(
        "InventoryOperation",
        primaryjoin="InventoryOperationTax.main_correlative == InventoryOperation.correlative",
        backref="inventory_operation_taxes",
    )
    tax_type1 = db.relationship(
        "TaxType",
        primaryjoin="InventoryOperationTax.tax_type == TaxType.code",
        backref="inventory_operation_taxes",
    )
    tax1 = db.relationship(
        "Tax",
        primaryjoin="InventoryOperationTax.taxe_code == Tax.code",
        backref="inventory_operation_taxes",
    )


class Location(db.Model):
    __tablename__ = "locations"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    parent_store = db.Column(db.ForeignKey("public.store.code", onupdate="CASCADE"))

    store = db.relationship(
        "Store", primaryjoin="Location.parent_store == Store.code", backref="locations"
    )


class Mark(db.Model):
    __tablename__ = "marks"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class Menu(db.Model):
    __tablename__ = "menus"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    father_menu = db.Column(db.String, nullable=False, server_default=db.FetchedValue())
    visible = db.Column(db.Boolean, server_default=db.FetchedValue())


class ModuleNumbering(db.Model):
    __tablename__ = "module_numbering"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class Numbering(db.Model):
    __tablename__ = "numbering"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True, nullable=False)
    last_number = db.Column(db.Integer)
    module = db.Column(
        db.ForeignKey(
            "public.module_numbering.code", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    description = db.Column(db.String)
    last_number_in_wait = db.Column(db.Integer)
    factor = db.Column(db.Integer)
    alias = db.Column(db.String)
    internal_use = db.Column(db.Boolean, server_default=db.FetchedValue())

    module_numbering = db.relationship(
        "ModuleNumbering",
        primaryjoin="Numbering.module == ModuleNumbering.code",
        backref="numberings",
    )


class Numeration(db.Model):
    __tablename__ = "numeration"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    prefix = db.Column(db.String)
    last_number = db.Column(db.Integer)


class Origin(db.Model):
    __tablename__ = "origin"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class PersonType(db.Model):
    __tablename__ = "person_type"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class PettyCash(db.Model):
    __tablename__ = "petty_cash"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    account_accounting = db.Column(
        db.ForeignKey(
            "public.account_accounting.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    conciliation_period = db.Column(db.String)
    initial_balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    credits = db.Column(db.Double(53), server_default=db.FetchedValue())
    debits = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    last_in = db.Column(db.Integer, server_default=db.FetchedValue())
    last_out = db.Column(db.Integer, server_default=db.FetchedValue())
    coin = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    account_accounting1 = db.relationship(
        "AccountAccounting",
        primaryjoin="PettyCash.account_accounting == AccountAccounting.code",
        backref="petty_cash",
    )
    coin1 = db.relationship(
        "Coin", primaryjoin="PettyCash.coin == Coin.code", backref="petty_cash"
    )


class PettyCashConciliation(db.Model):
    __tablename__ = "petty_cash_conciliation"
    __table_args__ = (
        db.UniqueConstraint("petty_cash", "period_conciliation"),
        {"schema": "public", "extend_existing": True},
    )

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    petty_cash = db.Column(
        db.ForeignKey("public.petty_cash.code", ondelete="CASCADE", onupdate="CASCADE")
    )
    period_conciliation = db.Column(db.String)
    register_date = db.Column(db.Date)
    user_code = db.Column(db.String)
    initial_balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    credits = db.Column(db.Double(53), server_default=db.FetchedValue())
    debits = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    petty_cash_balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance_difference = db.Column(db.Double(53), server_default=db.FetchedValue())
    in_count = db.Column(db.Integer, server_default=db.FetchedValue())
    in_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    out_count = db.Column(db.Integer, server_default=db.FetchedValue())
    out_amount = db.Column(db.Double(53), server_default=db.FetchedValue())

    petty_cash1 = db.relationship(
        "PettyCash",
        primaryjoin="PettyCashConciliation.petty_cash == PettyCash.code",
        backref="petty_cash_conciliations",
    )


class PettyCashTransactionAccountDetail(db.Model):
    __tablename__ = "petty_cash_transaction_account_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.petty_cash_transactions.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    line = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    account_accounting = db.Column(
        db.ForeignKey(
            "public.account_accounting.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    credit = db.Column(db.Double(53))
    debit = db.Column(db.Double(53))

    account_accounting1 = db.relationship(
        "AccountAccounting",
        primaryjoin="PettyCashTransactionAccountDetail.account_accounting == AccountAccounting.code",
        backref="petty_cash_transaction_account_details",
    )
    petty_cash_transaction = db.relationship(
        "PettyCashTransaction",
        primaryjoin="PettyCashTransactionAccountDetail.main_correlative == PettyCashTransaction.correlative",
        backref="petty_cash_transaction_account_details",
    )


class PettyCashTransaction(db.Model):
    __tablename__ = "petty_cash_transactions"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    petty_cash = db.Column(
        db.ForeignKey("public.petty_cash.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    operation_type = db.Column(db.String)
    reference_number = db.Column(db.String)
    description = db.Column(db.String)
    operation_comments = db.Column(db.String)
    amount = db.Column(db.Double(53))
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    credit = db.Column(db.Double(53))
    debit = db.Column(db.Double(53))
    ready_to_conciliate = db.Column(db.Boolean, server_default=db.FetchedValue())
    correlative_conciliation = db.Column(
        db.Integer, nullable=False, server_default=db.FetchedValue()
    )

    petty_cash1 = db.relationship(
        "PettyCash",
        primaryjoin="PettyCashTransaction.petty_cash == PettyCash.code",
        backref="petty_cash_transactions",
    )


class PictureGallery(db.Model):
    __tablename__ = "picture_gallery"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    image = db.Column(db.LargeBinary)
    description = db.Column(db.String)
    image_type = db.Column(db.String)


class ProdFormula(db.Model):
    __tablename__ = "prod_formulas"
    __table_args__ = {"schema": "public", "extend_existing": True}

    id = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    code = db.Column(db.String, unique=True)
    description = db.Column(db.String)
    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    product_unit = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    qty = db.Column(db.Double(53))
    status = db.Column(db.Boolean)

    product = db.relationship(
        "Product",
        primaryjoin="ProdFormula.product_code == Product.code",
        backref="prod_formulas",
    )
    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="ProdFormula.product_unit == ProductsUnit.correlative",
        backref="prod_formulas",
    )


class ProdFormulasDetail(db.Model):
    __tablename__ = "prod_formulas_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    formula_id = db.Column(
        db.ForeignKey(
            "public.prod_formulas.id", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    id = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    product_unit = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    qty = db.Column(db.Double(53))
    status = db.Column(db.Boolean)

    formula = db.relationship(
        "ProdFormula",
        primaryjoin="ProdFormulasDetail.formula_id == ProdFormula.id",
        backref="prod_formulas_details",
    )
    product = db.relationship(
        "Product",
        primaryjoin="ProdFormulasDetail.product_code == Product.code",
        backref="prod_formulas_details",
    )
    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="ProdFormulasDetail.product_unit == ProductsUnit.correlative",
        backref="prod_formulas_details",
    )


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    short_name = db.Column(db.String)
    mark = db.Column(db.String)
    model = db.Column(db.String)
    referenc = db.Column(db.String)
    department = db.Column(
        db.ForeignKey("public.department.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    days_warranty = db.Column(db.Integer)
    sale_tax = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    buy_tax = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    rounding_type = db.Column(db.Integer)
    costing_type = db.Column(db.Integer)
    discount = db.Column(db.Double(53))
    max_discount = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    minimal_sale = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    maximal_sale = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    status = db.Column(
        db.ForeignKey("public.status.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    origin = db.Column(
        db.ForeignKey("public.origin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    take_department_utility = db.Column(db.Boolean)
    allow_decimal = db.Column(db.Boolean)
    edit_name = db.Column(db.Boolean)
    sale_price = db.Column(db.Integer)
    product_type = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    technician = db.Column(
        db.ForeignKey(
            "public.technician.code", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        server_default=db.FetchedValue(),
    )
    request_technician = db.Column(db.Boolean, server_default=db.FetchedValue())
    serialized = db.Column(db.Boolean, server_default=db.FetchedValue())
    request_details = db.Column(db.Boolean, server_default=db.FetchedValue())
    request_amount = db.Column(db.Boolean, server_default=db.FetchedValue())
    coin = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    allow_negative_stock = db.Column(db.Boolean, server_default=db.FetchedValue())
    use_scale = db.Column(db.Boolean, server_default=db.FetchedValue())
    add_unit_description = db.Column(db.Boolean, server_default=db.FetchedValue())
    use_lots = db.Column(db.Boolean, server_default=db.FetchedValue())
    lots_order = db.Column(db.Integer, server_default=db.FetchedValue())
    minimal_stock = db.Column(db.Double(53), server_default=db.FetchedValue())
    notify_minimal_stock = db.Column(db.Boolean, server_default=db.FetchedValue())
    size = db.Column(db.String, server_default=db.FetchedValue())
    color = db.Column(db.String, server_default=db.FetchedValue())
    extract_net_from_unit_cost_plus_tax = db.Column(
        db.Boolean, server_default=db.FetchedValue()
    )
    extract_net_from_unit_price_plus_tax = db.Column(
        db.Boolean, server_default=db.FetchedValue()
    )
    maximum_stock = db.Column(db.Double(53), server_default=db.FetchedValue())

    tax = db.relationship(
        "Tax", primaryjoin="Product.buy_tax == Tax.code", backref="tax_products"
    )
    coin1 = db.relationship(
        "Coin", primaryjoin="Product.coin == Coin.code", backref="products"
    )
    department1 = db.relationship(
        "Department",
        primaryjoin="Product.department == Department.code",
        backref="products",
    )
    origin1 = db.relationship(
        "Origin", primaryjoin="Product.origin == Origin.code", backref="products"
    )
    tax1 = db.relationship(
        "Tax", primaryjoin="Product.sale_tax == Tax.code", backref="tax_products_0"
    )
    status1 = db.relationship(
        "Status", primaryjoin="Product.status == Status.code", backref="products"
    )
    technician1 = db.relationship(
        "Technician",
        primaryjoin="Product.technician == Technician.code",
        backref="products",
    )


class ProductsImage(Product):
    __tablename__ = "products_image"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    image_type = db.Column(db.String)
    product_image = db.Column(db.LargeBinary)


class RestPosProduct(Product):
    __tablename__ = "rest_pos_products"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    index_order = db.Column(db.Integer)


class ProductsCode(db.Model):
    __tablename__ = "products_codes"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    other_code = db.Column(db.String, primary_key=True)
    code_type = db.Column(db.String, server_default=db.FetchedValue())

    product = db.relationship(
        "Product",
        primaryjoin="ProductsCode.main_code == Product.code",
        backref="products_codes",
    )


class ProductsCommission(db.Model):
    __tablename__ = "products_commission"
    __table_args__ = {"schema": "public", "extend_existing": True}

    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    comission_type = db.Column(db.String, primary_key=True, nullable=False)
    value_type = db.Column(db.String)
    perc_maximum_price = db.Column(db.Double(53))
    perc_offer_price = db.Column(db.Double(53))
    perc_higher_price = db.Column(db.Double(53))
    perc_minimum_price = db.Column(db.Double(53))
    perc_variable_price = db.Column(db.Double(53))

    product = db.relationship(
        "Product",
        primaryjoin="ProductsCommission.product_code == Product.code",
        backref="products_commissions",
    )


class ProductsLot(db.Model):
    __tablename__ = "products_lots"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    lot_number = db.Column(db.String)
    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE")
    )
    entry_date = db.Column(db.Date)
    entry_module = db.Column(db.String)
    entry_correlative = db.Column(db.Integer)
    entry_amount = db.Column(db.Double(53))
    expire = db.Column(db.Boolean)
    expire_date = db.Column(db.Date)
    apply_prices = db.Column(db.Boolean)
    elaboration_date = db.Column(db.Date)

    product = db.relationship(
        "Product",
        primaryjoin="ProductsLot.product_code == Product.code",
        backref="products_lots",
    )


class ProductsLotsStock(db.Model):
    __tablename__ = "products_lots_stock"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.products_lots.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    stock = db.Column(db.Double(53), server_default=db.FetchedValue())
    ordered_stock = db.Column(db.Double(53), server_default=db.FetchedValue())
    committed_stock = db.Column(db.Double(53), server_default=db.FetchedValue())

    location = db.relationship(
        "Location",
        primaryjoin="ProductsLotsStock.locations == Location.code",
        backref="products_lots_stocks",
    )
    products_lot = db.relationship(
        "ProductsLot",
        primaryjoin="ProductsLotsStock.main_correlative == ProductsLot.correlative",
        backref="products_lots_stocks",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="ProductsLotsStock.store == Store.code",
        backref="products_lots_stocks",
    )


class ProductsLotsUnit(db.Model):
    __tablename__ = "products_lots_units"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    lots_correlative = db.Column(
        db.ForeignKey(
            "public.products_lots.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    unitary_cost = db.Column(db.Double(53))
    calculated_cost = db.Column(db.Double(53))
    average_cost = db.Column(db.Double(53))
    perc_waste_cost = db.Column(db.Double(53))
    perc_handling_cost = db.Column(db.Double(53))
    perc_operating_cost = db.Column(db.Double(53))
    perc_additional_cost = db.Column(db.Double(53))
    maximum_price = db.Column(db.Double(53))
    offer_price = db.Column(db.Double(53))
    higher_price = db.Column(db.Double(53))
    minimum_price = db.Column(db.Double(53))
    perc_maximum_price = db.Column(db.Double(53))
    perc_offer_price = db.Column(db.Double(53))
    perc_higher_price = db.Column(db.Double(53))
    perc_minimum_price = db.Column(db.Double(53))
    perc_freight_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    perc_discount_provider = db.Column(db.Double(53), server_default=db.FetchedValue())

    products_lot = db.relationship(
        "ProductsLot",
        primaryjoin="ProductsLotsUnit.lots_correlative == ProductsLot.correlative",
        backref="products_lots_units",
    )
    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="ProductsLotsUnit.main_correlative == ProductsUnit.correlative",
        backref="products_lots_units",
    )


class ProductsPart(db.Model):
    __tablename__ = "products_parts"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE")
    )
    part_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    unit = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    amount = db.Column(db.Double(53))
    line = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    cost_type = db.Column(db.String, server_default=db.FetchedValue())

    product = db.relationship(
        "Product",
        primaryjoin="ProductsPart.main_code == Product.code",
        backref="product_products_parts",
    )
    product1 = db.relationship(
        "Product",
        primaryjoin="ProductsPart.part_code == Product.code",
        backref="product_products_parts_0",
    )
    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="ProductsPart.unit == ProductsUnit.correlative",
        backref="products_parts",
    )


class ProductsProvider(db.Model):
    __tablename__ = "products_provider"
    __table_args__ = {"schema": "public", "extend_existing": True}

    line = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE")
    )
    provider_code = db.Column(
        db.ForeignKey("public.provider.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    unitary_cost = db.Column(db.Double(53))
    document_type = db.Column(db.String)
    document_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    unit = db.Column(db.Integer, server_default=db.FetchedValue())
    coin_code = db.Column(db.String, server_default=db.FetchedValue())
    related_line = db.Column(db.Integer, server_default=db.FetchedValue())

    product = db.relationship(
        "Product",
        primaryjoin="ProductsProvider.product_code == Product.code",
        backref="products_providers",
    )
    provider = db.relationship(
        "Provider",
        primaryjoin="ProductsProvider.provider_code == Provider.code",
        backref="products_providers",
    )


class ProductsSerial(db.Model):
    __tablename__ = "products_serial"
    __table_args__ = {"schema": "public", "extend_existing": True}

    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE")
    )
    line = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    serial_no = db.Column(db.String)
    stock = db.Column(db.Double(53))
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    correlative_in = db.Column(db.Integer)
    module_in = db.Column(db.String)

    location = db.relationship(
        "Location",
        primaryjoin="ProductsSerial.locations == Location.code",
        backref="products_serials",
    )
    product = db.relationship(
        "Product",
        primaryjoin="ProductsSerial.product_code == Product.code",
        backref="products_serials",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="ProductsSerial.store == Store.code",
        backref="products_serials",
    )


class ProductsStatistic(db.Model):
    __tablename__ = "products_statistics"
    __table_args__ = {"schema": "public", "extend_existing": True}

    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    statistic_date = db.Column(db.Date, primary_key=True, nullable=False)
    initial_stock = db.Column(db.Double(53), server_default=db.FetchedValue())
    load_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    download_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    load_amount_by_transfer = db.Column(db.Double(53), server_default=db.FetchedValue())
    download_amount_by_transfer = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    load_amount_by_adjustment = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    download_amount_by_adjustment = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    sales_delivery_note_amount = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    sales_bill_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    sales_devolution_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    sales_credit_note_amount = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    shopping_delivery_note_amount = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    shopping_bill_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    shopping_devolution_amount = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    shopping_credit_note_amount = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    final_stock = db.Column(db.Double(53), server_default=db.FetchedValue())
    unitary_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    average_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    calculated_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    maximum_price = db.Column(db.Double(53), server_default=db.FetchedValue())
    offer_price = db.Column(db.Double(53), server_default=db.FetchedValue())
    higher_price = db.Column(db.Double(53), server_default=db.FetchedValue())
    minimum_price = db.Column(db.Double(53), server_default=db.FetchedValue())
    period = db.Column(db.String)
    sales_income_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    internal_download_amount = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    shopping_expense_amount = db.Column(db.Double(53), server_default=db.FetchedValue())

    location = db.relationship(
        "Location",
        primaryjoin="ProductsStatistic.locations == Location.code",
        backref="products_statistics",
    )
    product = db.relationship(
        "Product",
        primaryjoin="ProductsStatistic.product_code == Product.code",
        backref="products_statistics",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="ProductsStatistic.store == Store.code",
        backref="products_statistics",
    )


class ProductsStock(db.Model):
    __tablename__ = "products_stock"
    __table_args__ = {"schema": "public", "extend_existing": True}

    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    stock = db.Column(db.Double(53))
    ordered_stock = db.Column(db.Double(53), server_default=db.FetchedValue())
    committed_stock = db.Column(db.Double(53), server_default=db.FetchedValue())

    location = db.relationship(
        "Location",
        primaryjoin="ProductsStock.locations == Location.code",
        backref="products_stocks",
    )
    product = db.relationship(
        "Product",
        primaryjoin="ProductsStock.product_code == Product.code",
        backref="products_stocks",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="ProductsStock.store == Store.code",
        backref="products_stocks",
    )


class ProductsUnit(db.Model):
    __tablename__ = "products_units"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    unit = db.Column(
        db.ForeignKey("public.units.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE")
    )
    main_unit = db.Column(db.Boolean)
    conversion_factor = db.Column(db.Double(53))
    unit_type = db.Column(db.Integer)
    show_in_screen = db.Column(db.Boolean)
    is_for_buy = db.Column(db.Boolean)
    is_for_sale = db.Column(db.Boolean)
    unitary_cost = db.Column(db.Double(53))
    calculated_cost = db.Column(db.Double(53))
    average_cost = db.Column(db.Double(53))
    perc_waste_cost = db.Column(db.Double(53))
    perc_handling_cost = db.Column(db.Double(53))
    perc_operating_cost = db.Column(db.Double(53))
    perc_additional_cost = db.Column(db.Double(53))
    maximum_price = db.Column(db.Double(53))
    offer_price = db.Column(db.Double(53))
    higher_price = db.Column(db.Double(53))
    minimum_price = db.Column(db.Double(53))
    perc_maximum_price = db.Column(db.Double(53))
    perc_offer_price = db.Column(db.Double(53))
    perc_higher_price = db.Column(db.Double(53))
    perc_minimum_price = db.Column(db.Double(53))
    perc_freight_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    perc_discount_provider = db.Column(db.Double(53), server_default=db.FetchedValue())
    lenght = db.Column(db.Double(53), server_default=db.FetchedValue())
    height = db.Column(db.Double(53), server_default=db.FetchedValue())
    width = db.Column(db.Double(53), server_default=db.FetchedValue())
    weight = db.Column(db.Double(53), server_default=db.FetchedValue())
    capacitance = db.Column(db.Double(53), server_default=db.FetchedValue())

    product = db.relationship(
        "Product",
        primaryjoin="ProductsUnit.product_code == Product.code",
        backref="products_units",
    )
    unit1 = db.relationship(
        "Unit", primaryjoin="ProductsUnit.unit == Unit.code", backref="products_units"
    )


class Profile(db.Model):
    __tablename__ = "profile"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    menus_inactive = db.Column(db.String)


class PropertiesGroup(db.Model):
    __tablename__ = "properties_group"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class Provider(db.Model):
    __tablename__ = "provider"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    address = db.Column(db.String)
    provider_id = db.Column(db.String)
    email = db.Column(db.String)
    phone = db.Column(db.String)
    contact = db.Column(db.String)
    country = db.Column(
        db.ForeignKey("public.countrys.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    province = db.Column(
        db.ForeignKey("public.provinces.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    city = db.Column(
        db.ForeignKey("public.citys.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    town = db.Column(
        db.ForeignKey("public.towns.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    credit_days = db.Column(db.Integer)
    credit_limit = db.Column(db.Double(53))
    provider_type = db.Column(
        db.ForeignKey(
            "public.person_type.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    status = db.Column(db.String)
    domiciled = db.Column(db.Integer)
    percent_tax_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_municipal_retention = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_tax_agent = db.Column(db.Boolean, server_default=db.FetchedValue())
    retention_municipal_agent = db.Column(db.Boolean, server_default=db.FetchedValue())
    retention_islr_agent = db.Column(db.Boolean, server_default=db.FetchedValue())
    perception_igtf_agent = db.Column(db.Boolean, server_default=db.FetchedValue())

    city1 = db.relationship(
        "City", primaryjoin="Provider.city == City.code", backref="providers"
    )
    country1 = db.relationship(
        "Country", primaryjoin="Provider.country == Country.code", backref="providers"
    )
    person_type = db.relationship(
        "PersonType",
        primaryjoin="Provider.provider_type == PersonType.code",
        backref="providers",
    )
    province1 = db.relationship(
        "Province",
        primaryjoin="Provider.province == Province.code",
        backref="providers",
    )
    town1 = db.relationship(
        "Town", primaryjoin="Provider.town == Town.code", backref="providers"
    )


class ProvidersBalance(db.Model):
    __tablename__ = "providers_balance"
    __table_args__ = {"schema": "public", "extend_existing": True}

    provider = db.Column(
        db.ForeignKey("public.provider.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    emission_date = db.Column(db.Date, primary_key=True, nullable=False)
    initial_balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    credits = db.Column(db.Double(53), server_default=db.FetchedValue())
    debits = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())

    provider1 = db.relationship(
        "Provider",
        primaryjoin="ProvidersBalance.provider == Provider.code",
        backref="providers_balances",
    )


class Province(db.Model):
    __tablename__ = "provinces"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class Receivable(db.Model):
    __tablename__ = "receivable"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    operation_type = db.Column(db.String)
    document_no = db.Column(db.String)
    control_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time(True))
    client_code = db.Column(
        db.ForeignKey("public.clients.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    client_name = db.Column(db.String)
    client_id = db.Column(db.String)
    client_address = db.Column(db.String)
    client_phone = db.Column(db.String)
    client_name_fiscal = db.Column(db.Integer)
    credit_days = db.Column(db.Integer)
    expiration_date = db.Column(db.Date)
    description = db.Column(db.String)
    operation_comments = db.Column(db.String)
    seller = db.Column(
        db.ForeignKey("public.sellers.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    debit = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_municipal = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_aditional = db.Column(db.Double(53), server_default=db.FetchedValue())
    payment_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    advance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    begin_used = db.Column(db.Boolean, server_default=db.FetchedValue())
    repayment_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    canceled = db.Column(db.Boolean, nullable=False, server_default=db.FetchedValue())
    fiscal_impresion = db.Column(db.Boolean, server_default=db.FetchedValue())
    fiscal_printer_serial = db.Column(db.String, server_default=db.FetchedValue())
    fiscal_printer_z = db.Column(db.String, server_default=db.FetchedValue())
    fiscal_printer_date = db.Column(db.DateTime)
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    indexing_coin = db.Column(db.String, server_default=db.FetchedValue())
    indexing_factor = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing_debit = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing_credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing = db.Column(db.Boolean, server_default=db.FetchedValue())
    debit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing_correlative_origin = db.Column(
        db.Integer, server_default=db.FetchedValue()
    )
    indexing_module_origin = db.Column(db.String, server_default=db.FetchedValue())
    indexing_register_factor_rel = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    total_exempt = db.Column(db.Double(53), server_default=db.FetchedValue())
    base_igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    igtf = db.Column(db.Double(53), server_default=db.FetchedValue())

    client = db.relationship(
        "Client",
        primaryjoin="Receivable.client_code == Client.code",
        backref="receivables",
    )
    coin = db.relationship(
        "Coin", primaryjoin="Receivable.coin_code == Coin.code", backref="receivables"
    )
    seller1 = db.relationship(
        "Seller", primaryjoin="Receivable.seller == Seller.code", backref="receivables"
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="Receivable.station == Station.code",
        backref="receivables",
    )
    user = db.relationship(
        "User", primaryjoin="Receivable.user_code == User.code", backref="receivables"
    )


class ReceivableReturnedCheck(Receivable):
    __tablename__ = "receivable_returned_check"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.receivable.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
    )
    check_date = db.Column(db.Date)
    check_number = db.Column(db.String)
    bank = db.Column(
        db.ForeignKey("public.banks.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    bank1 = db.relationship(
        "Bank",
        primaryjoin="ReceivableReturnedCheck.bank == Bank.code",
        backref="receivable_returned_checks",
    )


class ReceivableCoin(db.Model):
    __tablename__ = "receivable_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.receivable.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    factor_type = db.Column(db.Integer)
    factor_aliquot = db.Column(db.Double(53))
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    debit = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_municipal = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_aditional = db.Column(db.Double(53), server_default=db.FetchedValue())
    payment_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    advance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    repayment_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing_debit = db.Column(db.Double(53), server_default=db.FetchedValue())
    indexing_credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    debit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_exempt = db.Column(db.Double(53), server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin",
        primaryjoin="ReceivableCoin.coin_code == Coin.code",
        backref="receivable_coins",
    )
    receivable = db.relationship(
        "Receivable",
        primaryjoin="ReceivableCoin.main_correlative == Receivable.correlative",
        backref="receivable_coins",
    )


class ReceivableDetail(db.Model):
    __tablename__ = "receivable_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.receivable.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_related = db.Column(
        db.ForeignKey(
            "public.receivable.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(db.Integer, nullable=False, server_default=db.FetchedValue())
    module_related = db.Column(db.String)
    balance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax = db.Column(db.Double(53))
    retention_islr = db.Column(db.Double(53))
    retention_municipal = db.Column(db.Double(53))
    credit_note = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    relation_type = db.Column(
        db.String, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )

    receivable = db.relationship(
        "Receivable",
        primaryjoin="ReceivableDetail.correlative_related == Receivable.correlative",
        backref="receivable_receivable_details",
    )
    receivable1 = db.relationship(
        "Receivable",
        primaryjoin="ReceivableDetail.main_correlative == Receivable.correlative",
        backref="receivable_receivable_details_0",
    )


class ReceivableDetailsCoin(db.Model):
    __tablename__ = "receivable_details_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.receivable.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_related = db.Column(
        db.ForeignKey(
            "public.receivable.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    main_line = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String)
    coin_code = db.Column(db.String, primary_key=True, nullable=False)
    balance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax = db.Column(db.Double(53))
    retention_islr = db.Column(db.Double(53))
    retention_municipal = db.Column(db.Double(53))
    credit_note = db.Column(db.Double(53), server_default=db.FetchedValue())
    balance = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())

    receivable = db.relationship(
        "Receivable",
        primaryjoin="ReceivableDetailsCoin.correlative_related == Receivable.correlative",
        backref="receivable_receivable_details_coins",
    )
    receivable1 = db.relationship(
        "Receivable",
        primaryjoin="ReceivableDetailsCoin.main_correlative == Receivable.correlative",
        backref="receivable_receivable_details_coins_0",
    )


class ReceivableTax(db.Model):
    __tablename__ = "receivable_taxes"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.receivable.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    taxe_code = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    aliquot = db.Column(db.Double(53))
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    line = db.Column(db.Integer, nullable=False, server_default=db.FetchedValue())
    tax_type = db.Column(
        db.ForeignKey("public.tax_types.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    receivable = db.relationship(
        "Receivable",
        primaryjoin="ReceivableTax.main_correlative == Receivable.correlative",
        backref="receivable_taxes",
    )
    tax_type1 = db.relationship(
        "TaxType",
        primaryjoin="ReceivableTax.tax_type == TaxType.code",
        backref="receivable_taxes",
    )
    tax1 = db.relationship(
        "Tax",
        primaryjoin="ReceivableTax.taxe_code == Tax.code",
        backref="receivable_taxes",
    )


class ReceivableTaxesCoin(db.Model):
    __tablename__ = "receivable_taxes_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_taxe_code"],
            [
                "public.receivable_taxes.main_correlative",
                "public.receivable_taxes.taxe_code",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_taxe_code = db.Column(db.String, primary_key=True, nullable=False)
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    main_line = db.Column(db.Integer)

    coin = db.relationship(
        "Coin",
        primaryjoin="ReceivableTaxesCoin.coin_code == Coin.code",
        backref="receivable_taxes_coins",
    )
    receivable_tax = db.relationship(
        "ReceivableTax",
        primaryjoin="and_(ReceivableTaxesCoin.main_correlative == ReceivableTax.main_correlative, ReceivableTaxesCoin.main_taxe_code == ReceivableTax.taxe_code)",
        backref="receivable_taxes_coins",
    )


class RecyclerRetentionIslrClient(db.Model):
    __tablename__ = "recycler_retention_islr_clients"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(db.Integer, primary_key=True)
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    reception_date = db.Column(db.Date)
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    client_code = db.Column(db.String)
    client_id = db.Column(db.String)
    client_name = db.Column(db.String)
    client_phone = db.Column(db.String)
    client_address = db.Column(db.String)


class RecyclerRetentionIslrClientsDetail(db.Model):
    __tablename__ = "recycler_retention_islr_clients_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_retention_islr_clients.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    line = db.Column(db.Integer, primary_key=True)
    code_islr = db.Column(
        db.ForeignKey("public.codes_islr.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    calculation_base = db.Column(db.Double(53))
    percent_retention = db.Column(db.Double(53))
    sustraendo = db.Column(db.Double(53))
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    service_description = db.Column(db.String)
    module_related = db.Column(db.String)
    correlative_related = db.Column(db.Integer)
    code_selected = db.Column(db.String)

    codes_islr = db.relationship(
        "CodesIslr",
        primaryjoin="RecyclerRetentionIslrClientsDetail.code_islr == CodesIslr.code",
        backref="recycler_retention_islr_clients_details",
    )
    recycler_retention_islr_client = db.relationship(
        "RecyclerRetentionIslrClient",
        primaryjoin="RecyclerRetentionIslrClientsDetail.main_correlative == RecyclerRetentionIslrClient.correlative",
        backref="recycler_retention_islr_clients_details",
    )


class RecyclerRetentionIslrProvider(db.Model):
    __tablename__ = "recycler_retention_islr_provider"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(db.Integer, primary_key=True)
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    provider_id = db.Column(db.String)
    provider_name = db.Column(db.String)
    provider_phone = db.Column(db.String)
    provider_address = db.Column(db.String)
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    provider_code = db.Column(db.String)


class RecyclerRetentionIslrProviderDetail(db.Model):
    __tablename__ = "recycler_retention_islr_provider_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_retention_islr_provider.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    line = db.Column(db.Integer, primary_key=True)
    code_islr = db.Column(
        db.ForeignKey("public.codes_islr.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    calculation_base = db.Column(db.Double(53))
    percent_retention = db.Column(db.Double(53))
    sustraendo = db.Column(db.Double(53))
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    service_description = db.Column(db.String)
    module_related = db.Column(db.String)
    correlative_related = db.Column(db.Integer)
    code_selected = db.Column(db.String)

    codes_islr = db.relationship(
        "CodesIslr",
        primaryjoin="RecyclerRetentionIslrProviderDetail.code_islr == CodesIslr.code",
        backref="recycler_retention_islr_provider_details",
    )
    recycler_retention_islr_provider = db.relationship(
        "RecyclerRetentionIslrProvider",
        primaryjoin="RecyclerRetentionIslrProviderDetail.main_correlative == RecyclerRetentionIslrProvider.correlative",
        backref="recycler_retention_islr_provider_details",
    )


class RecyclerRetentionMunicipalClient(db.Model):
    __tablename__ = "recycler_retention_municipal_clients"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(db.Integer, primary_key=True)
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    reception_date = db.Column(db.Date)
    percent_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    client_code = db.Column(db.String)
    client_id = db.Column(db.String)
    client_name = db.Column(db.String)
    client_phone = db.Column(db.String)
    client_address = db.Column(db.String)


class RecyclerRetentionMunicipalClientsDetail(db.Model):
    __tablename__ = "recycler_retention_municipal_clients_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_retention_municipal_clients.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    related_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    related_module = db.Column(db.String, primary_key=True, nullable=False)
    line = db.Column(db.Integer, nullable=False, unique=True)
    related_taxes_line = db.Column(db.Integer, primary_key=True, nullable=False)
    total_retention = db.Column(db.Double(53))

    recycler_retention_municipal_client = db.relationship(
        "RecyclerRetentionMunicipalClient",
        primaryjoin="RecyclerRetentionMunicipalClientsDetail.main_correlative == RecyclerRetentionMunicipalClient.correlative",
        backref="recycler_retention_municipal_clients_details",
    )


class RecyclerRetentionMunicipalProvider(db.Model):
    __tablename__ = "recycler_retention_municipal_provider"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(db.Integer, primary_key=True)
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    provider_id = db.Column(db.String)
    provider_name = db.Column(db.String)
    provider_phone = db.Column(db.String)
    provider_address = db.Column(db.String)
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    percent_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    provider_code = db.Column(db.String)


class RecyclerRetentionMunicipalProviderDetail(db.Model):
    __tablename__ = "recycler_retention_municipal_provider_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_retention_municipal_provider.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    related_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    related_module = db.Column(db.String, primary_key=True, nullable=False)
    line = db.Column(db.Integer, unique=True)
    related_taxes_line = db.Column(db.Integer, primary_key=True, nullable=False)
    total_retention = db.Column(db.Double(53))

    recycler_retention_municipal_provider = db.relationship(
        "RecyclerRetentionMunicipalProvider",
        primaryjoin="RecyclerRetentionMunicipalProviderDetail.main_correlative == RecyclerRetentionMunicipalProvider.correlative",
        backref="recycler_retention_municipal_provider_details",
    )


class RecyclerRetentionTaxClient(db.Model):
    __tablename__ = "recycler_retention_tax_clients"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(db.Integer, primary_key=True)
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    reception_date = db.Column(db.Date)
    percent_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    client_code = db.Column(db.String)
    client_id = db.Column(db.String)
    client_name = db.Column(db.String)
    client_phone = db.Column(db.String)
    client_address = db.Column(db.String)


class RecyclerRetentionTaxClientsDetail(db.Model):
    __tablename__ = "recycler_retention_tax_clients_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.retention_tax_clients.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    related_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    related_module = db.Column(db.String, primary_key=True, nullable=False)
    line = db.Column(db.Integer, nullable=False, unique=True)
    related_taxes_line = db.Column(db.Integer, primary_key=True, nullable=False)
    total_retention = db.Column(db.Double(53))

    retention_tax_client = db.relationship(
        "RetentionTaxClient",
        primaryjoin="RecyclerRetentionTaxClientsDetail.main_correlative == RetentionTaxClient.correlative",
        backref="recycler_retention_tax_clients_details",
    )


class RecyclerRetentionTaxProvider(db.Model):
    __tablename__ = "recycler_retention_tax_provider"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(db.Integer, primary_key=True)
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    provider_id = db.Column(db.String)
    provider_name = db.Column(db.String)
    provider_phone = db.Column(db.String)
    provider_address = db.Column(db.String)
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    percent_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    provider_code = db.Column(db.String)


class RecyclerRetentionTaxProviderDetail(db.Model):
    __tablename__ = "recycler_retention_tax_provider_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_retention_tax_provider.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    related_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    related_module = db.Column(db.String, primary_key=True, nullable=False)
    line = db.Column(db.Integer, nullable=False, unique=True)
    related_taxes_line = db.Column(db.Integer, primary_key=True, nullable=False)
    total_retention = db.Column(db.Double(53))

    recycler_retention_tax_provider = db.relationship(
        "RecyclerRetentionTaxProvider",
        primaryjoin="RecyclerRetentionTaxProviderDetail.main_correlative == RecyclerRetentionTaxProvider.correlative",
        backref="recycler_retention_tax_provider_details",
    )


class RecyclerSalesDocumentsRel(db.Model):
    __tablename__ = "recycler_sales_documents_rel"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(db.Integer, nullable=False, unique=True)
    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_sales_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_related = db.Column(db.Integer, primary_key=True, nullable=False)
    module_related = db.Column(db.String, primary_key=True, nullable=False)

    recycler_sales_operation = db.relationship(
        "RecyclerSalesOperation",
        primaryjoin="RecyclerSalesDocumentsRel.main_correlative == RecyclerSalesOperation.correlative",
        backref="recycler_sales_documents_rels",
    )


class RecyclerSalesOperation(db.Model):
    __tablename__ = "recycler_sales_operation"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(db.Integer, primary_key=True)
    operation_type = db.Column(db.String)
    document_no = db.Column(db.String)
    control_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    register_date = db.Column(db.Date)
    client_code = db.Column(
        db.ForeignKey("public.clients.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    client_name = db.Column(db.String)
    client_id = db.Column(db.String)
    client_address = db.Column(db.String)
    client_phone = db.Column(db.String)
    client_name_fiscal = db.Column(db.Integer)
    seller = db.Column(
        db.ForeignKey("public.sellers.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    credit_days = db.Column(db.Integer)
    expiration_date = db.Column(db.Date)
    wait = db.Column(db.Boolean)
    description = db.Column(db.String)
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    begin_used = db.Column(db.Boolean, server_default=db.FetchedValue())
    total_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_freight = db.Column(db.Double(53), server_default=db.FetchedValue())
    freight = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    operation_comments = db.Column(db.String)
    type_price = db.Column(db.Integer, server_default=db.FetchedValue())
    total_net_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_count_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    pending = db.Column(db.Boolean)
    canceled = db.Column(db.Boolean, nullable=False, server_default=db.FetchedValue())
    freight_tax = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    freight_aliquot = db.Column(db.Double(53))
    total_retention_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention_municipal = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    total_retention_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_operation = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_islr_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_municipal_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    document_no_internal = db.Column(db.String, server_default=db.FetchedValue())
    fiscal_impresion = db.Column(db.Boolean, server_default=db.FetchedValue())
    fiscal_printer_serial = db.Column(db.String, server_default=db.FetchedValue())
    fiscal_printer_z = db.Column(db.String, server_default=db.FetchedValue())
    fiscal_printer_date = db.Column(db.DateTime)
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    sale_point = db.Column(db.Boolean, server_default=db.FetchedValue())
    address_send = db.Column(db.String)
    contact_send = db.Column(db.String)
    phone_send = db.Column(db.String)
    free_tax = db.Column(db.Boolean, server_default=db.FetchedValue())
    delivered = db.Column(db.Boolean, server_default=db.FetchedValue())
    total_weight = db.Column(db.Double(53), server_default=db.FetchedValue())
    restorant = db.Column(db.Boolean, server_default=db.FetchedValue())
    delete_date = db.Column(db.Date)
    delete_hour = db.Column(db.Time)
    delete_user = db.Column(db.String)
    delete_station = db.Column(db.String)

    client = db.relationship(
        "Client",
        primaryjoin="RecyclerSalesOperation.client_code == Client.code",
        backref="recycler_sales_operations",
    )
    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerSalesOperation.coin_code == Coin.code",
        backref="recycler_sales_operations",
    )
    tax = db.relationship(
        "Tax",
        primaryjoin="RecyclerSalesOperation.freight_tax == Tax.code",
        backref="recycler_sales_operations",
    )
    location = db.relationship(
        "Location",
        primaryjoin="RecyclerSalesOperation.locations == Location.code",
        backref="recycler_sales_operations",
    )
    seller1 = db.relationship(
        "Seller",
        primaryjoin="RecyclerSalesOperation.seller == Seller.code",
        backref="recycler_sales_operations",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="RecyclerSalesOperation.station == Station.code",
        backref="recycler_sales_operations",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="RecyclerSalesOperation.store == Store.code",
        backref="recycler_sales_operations",
    )
    user = db.relationship(
        "User",
        primaryjoin="RecyclerSalesOperation.user_code == User.code",
        backref="recycler_sales_operations",
    )


class RecyclerSalesOperationCoin(db.Model):
    __tablename__ = "recycler_sales_operation_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_sales_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    factor_type = db.Column(db.Integer)
    buy_aliquot = db.Column(db.Double(53))
    sales_aliquot = db.Column(db.Double(53))
    total_net_details = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_tax_details = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_details = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    discount = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    freight = db.Column(db.Double(53), nullable=False, server_default=db.FetchedValue())
    total_net = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_tax = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total = db.Column(db.Double(53), nullable=False, server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), nullable=False, server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), nullable=False, server_default=db.FetchedValue())
    total_net_cost = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_tax_cost = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_cost = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_operation = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_retention_tax = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_retention_municipal = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_retention_islr = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    retention_tax_prorration = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    retention_islr_prorration = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    retention_municipal_prorration = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )

    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerSalesOperationCoin.coin_code == Coin.code",
        backref="recycler_sales_operation_coins",
    )
    recycler_sales_operation = db.relationship(
        "RecyclerSalesOperation",
        primaryjoin="RecyclerSalesOperationCoin.main_correlative == RecyclerSalesOperation.correlative",
        backref="recycler_sales_operation_coins",
    )


class RecyclerSalesOperationDetail(db.Model):
    __tablename__ = "recycler_sales_operation_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_sales_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(db.Integer, primary_key=True, nullable=False, unique=True)
    code_product = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    description_product = db.Column(db.String)
    referenc = db.Column(db.String)
    mark = db.Column(db.String)
    model = db.Column(db.String)
    amount = db.Column(db.Double(53))
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    unit = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    conversion_factor = db.Column(db.Double(53))
    unit_type = db.Column(db.Integer)
    unitary_cost = db.Column(db.Double(53))
    sale_tax = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    sale_aliquot = db.Column(db.Double(53))
    price = db.Column(db.Double(53), server_default=db.FetchedValue())
    type_price = db.Column(db.Integer, server_default=db.FetchedValue())
    total_net_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    pending_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    buy_tax = db.Column(db.String)
    buy_aliquot = db.Column(db.Double(53))
    update_inventory = db.Column(db.Boolean, server_default=db.FetchedValue())
    amount_released_by_load_order = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    amount_discharged_by_load_delivery_note = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    product_type = db.Column(db.String)
    description = db.Column(db.String)
    technician = db.Column(
        db.ForeignKey(
            "public.technician.code", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        server_default=db.FetchedValue(),
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    total_weight = db.Column(db.Double(53), server_default=db.FetchedValue())

    product = db.relationship(
        "Product",
        primaryjoin="RecyclerSalesOperationDetail.code_product == Product.code",
        backref="recycler_sales_operation_details",
    )
    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerSalesOperationDetail.coin_code == Coin.code",
        backref="recycler_sales_operation_details",
    )
    location = db.relationship(
        "Location",
        primaryjoin="RecyclerSalesOperationDetail.locations == Location.code",
        backref="recycler_sales_operation_details",
    )
    recycler_sales_operation = db.relationship(
        "RecyclerSalesOperation",
        primaryjoin="RecyclerSalesOperationDetail.main_correlative == RecyclerSalesOperation.correlative",
        backref="recycler_sales_operation_details",
    )
    tax = db.relationship(
        "Tax",
        primaryjoin="RecyclerSalesOperationDetail.sale_tax == Tax.code",
        backref="recycler_sales_operation_details",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="RecyclerSalesOperationDetail.store == Store.code",
        backref="recycler_sales_operation_details",
    )
    technician1 = db.relationship(
        "Technician",
        primaryjoin="RecyclerSalesOperationDetail.technician == Technician.code",
        backref="recycler_sales_operation_details",
    )
    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="RecyclerSalesOperationDetail.unit == ProductsUnit.correlative",
        backref="recycler_sales_operation_details",
    )


class RecyclerSalesOperationDetailsLot(RecyclerSalesOperationDetail):
    __tablename__ = "recycler_sales_operation_details_lots"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.recycler_sales_operation_details.main_correlative",
                "public.recycler_sales_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    lot_number = db.Column(db.String)
    expire = db.Column(db.Boolean)
    expire_date = db.Column(db.Date)
    apply_prices = db.Column(db.Boolean)
    elaboration_date = db.Column(db.Date)
    lot_correlative = db.Column(db.Integer)


class RecyclerSalesOperationDetailsCoin(db.Model):
    __tablename__ = "recycler_sales_operation_details_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.recycler_sales_operation_details.main_correlative",
                "public.recycler_sales_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    unitary_cost = db.Column(db.Double(53))
    price = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerSalesOperationDetailsCoin.coin_code == Coin.code",
        backref="recycler_sales_operation_details_coins",
    )
    recycler_sales_operation_detail = db.relationship(
        "RecyclerSalesOperationDetail",
        primaryjoin="and_(RecyclerSalesOperationDetailsCoin.main_correlative == RecyclerSalesOperationDetail.main_correlative, RecyclerSalesOperationDetailsCoin.main_line == RecyclerSalesOperationDetail.line)",
        backref="recycler_sales_operation_details_coins",
    )


class RecyclerSalesOperationDetailsLoad(db.Model):
    __tablename__ = "recycler_sales_operation_details_load"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["load_line", "load_correlative"],
            [
                "public.recycler_sales_operation_details.line",
                "public.recycler_sales_operation_details.main_correlative",
            ],
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        db.ForeignKeyConstraint(
            ["main_line", "main_correlative"],
            [
                "public.recycler_sales_operation_details.line",
                "public.recycler_sales_operation_details.main_correlative",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_line = db.Column(db.Integer, primary_key=True)
    load_line = db.Column(db.Integer)
    main_correlative = db.Column(db.Integer)
    load_correlative = db.Column(db.Integer)
    load_amount = db.Column(db.Double(53), server_default=db.FetchedValue())

    recycler_sales_operation_detail = db.relationship(
        "RecyclerSalesOperationDetail",
        primaryjoin="and_(RecyclerSalesOperationDetailsLoad.load_line == RecyclerSalesOperationDetail.line, RecyclerSalesOperationDetailsLoad.load_correlative == RecyclerSalesOperationDetail.main_correlative)",
        backref="recyclersalesoperationdetail_recycler_sales_operation_details_loads",
    )
    recycler_sales_operation_detail1 = db.relationship(
        "RecyclerSalesOperationDetail",
        primaryjoin="and_(RecyclerSalesOperationDetailsLoad.main_line == RecyclerSalesOperationDetail.line, RecyclerSalesOperationDetailsLoad.main_correlative == RecyclerSalesOperationDetail.main_correlative)",
        backref="recyclersalesoperationdetail_recycler_sales_operation_details_loads_0",
    )


class RecyclerSalesOperationDetailsPart(db.Model):
    __tablename__ = "recycler_sales_operation_details_parts"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.recycler_sales_operation_details.main_correlative",
                "public.recycler_sales_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    line = db.Column(db.Integer, primary_key=True, nullable=False, unique=True)
    code_product = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    description_product = db.Column(db.String)
    referenc = db.Column(db.String)
    mark = db.Column(db.String)
    model = db.Column(db.String)
    show_line = db.Column(db.Boolean)
    part_amount = db.Column(db.Double(53))
    total_amount = db.Column(db.Double(53))
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    unit = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    conversion_factor = db.Column(db.Double(53))
    unit_type = db.Column(db.Integer)
    unitary_cost = db.Column(db.Double(53))
    sale_tax = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    sale_aliquot = db.Column(db.Double(53))
    price = db.Column(db.Double(53), server_default=db.FetchedValue())
    type_price = db.Column(db.Integer, server_default=db.FetchedValue())
    total_net_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    buy_tax = db.Column(db.String)
    buy_aliquot = db.Column(db.Double(53))
    product_type = db.Column(db.String)
    description = db.Column(db.String)
    technician = db.Column(
        db.ForeignKey(
            "public.technician.code", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        server_default=db.FetchedValue(),
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    product = db.relationship(
        "Product",
        primaryjoin="RecyclerSalesOperationDetailsPart.code_product == Product.code",
        backref="recycler_sales_operation_details_parts",
    )
    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerSalesOperationDetailsPart.coin_code == Coin.code",
        backref="recycler_sales_operation_details_parts",
    )
    location = db.relationship(
        "Location",
        primaryjoin="RecyclerSalesOperationDetailsPart.locations == Location.code",
        backref="recycler_sales_operation_details_parts",
    )
    recycler_sales_operation_detail = db.relationship(
        "RecyclerSalesOperationDetail",
        primaryjoin="and_(RecyclerSalesOperationDetailsPart.main_correlative == RecyclerSalesOperationDetail.main_correlative, RecyclerSalesOperationDetailsPart.main_line == RecyclerSalesOperationDetail.line)",
        backref="recycler_sales_operation_details_parts",
    )
    tax = db.relationship(
        "Tax",
        primaryjoin="RecyclerSalesOperationDetailsPart.sale_tax == Tax.code",
        backref="recycler_sales_operation_details_parts",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="RecyclerSalesOperationDetailsPart.store == Store.code",
        backref="recycler_sales_operation_details_parts",
    )
    technician1 = db.relationship(
        "Technician",
        primaryjoin="RecyclerSalesOperationDetailsPart.technician == Technician.code",
        backref="recycler_sales_operation_details_parts",
    )
    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="RecyclerSalesOperationDetailsPart.unit == ProductsUnit.correlative",
        backref="recycler_sales_operation_details_parts",
    )


class RecyclerSalesOperationDetailsPartsCoin(db.Model):
    __tablename__ = "recycler_sales_operation_details_parts_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line", "main_part_line"],
            [
                "public.recycler_sales_operation_details_parts.main_correlative",
                "public.recycler_sales_operation_details_parts.main_line",
                "public.recycler_sales_operation_details_parts.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    main_part_line = db.Column(db.Integer, primary_key=True, nullable=False)
    unitary_cost = db.Column(db.Double(53))
    price = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerSalesOperationDetailsPartsCoin.coin_code == Coin.code",
        backref="recycler_sales_operation_details_parts_coins",
    )
    recycler_sales_operation_details_part = db.relationship(
        "RecyclerSalesOperationDetailsPart",
        primaryjoin="and_(RecyclerSalesOperationDetailsPartsCoin.main_correlative == RecyclerSalesOperationDetailsPart.main_correlative, RecyclerSalesOperationDetailsPartsCoin.main_line == RecyclerSalesOperationDetailsPart.main_line, RecyclerSalesOperationDetailsPartsCoin.main_part_line == RecyclerSalesOperationDetailsPart.line)",
        backref="recycler_sales_operation_details_parts_coins",
    )


class RecyclerSalesOperationDetailsSerial(db.Model):
    __tablename__ = "recycler_sales_operation_details_serials"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.recycler_sales_operation_details.main_correlative",
                "public.recycler_sales_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    line = db.Column(db.Integer, primary_key=True, nullable=False)
    serial_no = db.Column(db.String)
    serial_line = db.Column(db.Integer)
    load_by = db.Column(db.Integer)

    recycler_sales_operation_detail = db.relationship(
        "RecyclerSalesOperationDetail",
        primaryjoin="and_(RecyclerSalesOperationDetailsSerial.main_correlative == RecyclerSalesOperationDetail.main_correlative, RecyclerSalesOperationDetailsSerial.main_line == RecyclerSalesOperationDetail.line)",
        backref="recycler_sales_operation_details_serials",
    )


class RecyclerSalesOperationTax(db.Model):
    __tablename__ = "recycler_sales_operation_taxes"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_sales_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    taxe_code = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    aliquot = db.Column(db.Double(53))
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    line = db.Column(db.Integer, nullable=False)
    tax_type = db.Column(db.ForeignKey("public.tax_types.code", onupdate="CASCADE"))

    recycler_sales_operation = db.relationship(
        "RecyclerSalesOperation",
        primaryjoin="RecyclerSalesOperationTax.main_correlative == RecyclerSalesOperation.correlative",
        backref="recycler_sales_operation_taxes",
    )
    tax_type1 = db.relationship(
        "TaxType",
        primaryjoin="RecyclerSalesOperationTax.tax_type == TaxType.code",
        backref="recycler_sales_operation_taxes",
    )
    tax1 = db.relationship(
        "Tax",
        primaryjoin="RecyclerSalesOperationTax.taxe_code == Tax.code",
        backref="recycler_sales_operation_taxes",
    )


class RecyclerSalesOperationTaxesCoin(db.Model):
    __tablename__ = "recycler_sales_operation_taxes_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_taxe_code"],
            [
                "public.recycler_sales_operation_taxes.main_correlative",
                "public.recycler_sales_operation_taxes.taxe_code",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_taxe_code = db.Column(db.String, primary_key=True, nullable=False)
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    main_line = db.Column(db.Integer)

    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerSalesOperationTaxesCoin.coin_code == Coin.code",
        backref="recycler_sales_operation_taxes_coins",
    )
    recycler_sales_operation_tax = db.relationship(
        "RecyclerSalesOperationTax",
        primaryjoin="and_(RecyclerSalesOperationTaxesCoin.main_correlative == RecyclerSalesOperationTax.main_correlative, RecyclerSalesOperationTaxesCoin.main_taxe_code == RecyclerSalesOperationTax.taxe_code)",
        backref="recycler_sales_operation_taxes_coins",
    )


class RecyclerShoppingDocumentsRel(db.Model):
    __tablename__ = "recycler_shopping_documents_rel"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(db.Integer, unique=True)
    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_shopping_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_related = db.Column(db.Integer, primary_key=True, nullable=False)
    module_related = db.Column(db.String, primary_key=True, nullable=False)

    recycler_shopping_operation = db.relationship(
        "RecyclerShoppingOperation",
        primaryjoin="RecyclerShoppingDocumentsRel.main_correlative == RecyclerShoppingOperation.correlative",
        backref="recycler_shopping_documents_rels",
    )


class RecyclerShoppingOperation(db.Model):
    __tablename__ = "recycler_shopping_operation"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(db.Integer, primary_key=True)
    operation_type = db.Column(db.String)
    document_no = db.Column(db.String)
    control_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    reception_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    register_date = db.Column(db.Date)
    provider_code = db.Column(
        db.ForeignKey("public.provider.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    provider_name = db.Column(db.String)
    provider_id = db.Column(db.String)
    provider_address = db.Column(db.String)
    provider_phone = db.Column(db.String)
    credit_days = db.Column(db.Integer)
    expiration_date = db.Column(db.Date)
    wait = db.Column(db.Boolean)
    description = db.Column(db.String)
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    begin_used = db.Column(db.Boolean, server_default=db.FetchedValue())
    total_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_freight = db.Column(db.Double(53), server_default=db.FetchedValue())
    freight = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    operation_comments = db.Column(db.String)
    total_count_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    pending = db.Column(db.Boolean)
    buyer = db.Column(db.String)
    freight_tax = db.Column(db.String)
    freight_aliquot = db.Column(db.Double(53))
    total_retention_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention_municipal = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    total_retention_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_operation = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_islr_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_municipal_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    free_tax = db.Column(db.Boolean, nullable=False, server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerShoppingOperation.coin_code == Coin.code",
        backref="recycler_shopping_operations",
    )
    location = db.relationship(
        "Location",
        primaryjoin="RecyclerShoppingOperation.locations == Location.code",
        backref="recycler_shopping_operations",
    )
    provider = db.relationship(
        "Provider",
        primaryjoin="RecyclerShoppingOperation.provider_code == Provider.code",
        backref="recycler_shopping_operations",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="RecyclerShoppingOperation.station == Station.code",
        backref="recycler_shopping_operations",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="RecyclerShoppingOperation.store == Store.code",
        backref="recycler_shopping_operations",
    )
    user = db.relationship(
        "User",
        primaryjoin="RecyclerShoppingOperation.user_code == User.code",
        backref="recycler_shopping_operations",
    )


class RecyclerShoppingOperationCoin(db.Model):
    __tablename__ = "recycler_shopping_operation_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_shopping_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    factor_type = db.Column(db.Integer)
    buy_aliquot = db.Column(db.Double(53))
    sales_aliquot = db.Column(db.Double(53))
    total_net_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    freight = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention_municipal = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    total_retention_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_operation = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_islr_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_municipal_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )

    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerShoppingOperationCoin.coin_code == Coin.code",
        backref="recycler_shopping_operation_coins",
    )
    recycler_shopping_operation = db.relationship(
        "RecyclerShoppingOperation",
        primaryjoin="RecyclerShoppingOperationCoin.main_correlative == RecyclerShoppingOperation.correlative",
        backref="recycler_shopping_operation_coins",
    )


class RecyclerShoppingOperationDetail(db.Model):
    __tablename__ = "recycler_shopping_operation_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_shopping_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(db.Integer, primary_key=True, nullable=False, unique=True)
    code_product = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    description_product = db.Column(db.String)
    referenc = db.Column(db.String)
    mark = db.Column(db.String)
    model = db.Column(db.String)
    amount = db.Column(db.Double(53))
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    unit = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    conversion_factor = db.Column(db.Double(53))
    unit_type = db.Column(db.Integer)
    unitary_cost = db.Column(db.Double(53))
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    pending_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    buy_tax = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    buy_aliquot = db.Column(db.Double(53))
    update_inventory = db.Column(db.Boolean, server_default=db.FetchedValue())
    amount_released_by_load_order = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    amount_charged_by_load_delivery_note = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    product_type = db.Column(db.String)
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    change_price = db.Column(db.Boolean, server_default=db.FetchedValue())

    tax = db.relationship(
        "Tax",
        primaryjoin="RecyclerShoppingOperationDetail.buy_tax == Tax.code",
        backref="recycler_shopping_operation_details",
    )
    product = db.relationship(
        "Product",
        primaryjoin="RecyclerShoppingOperationDetail.code_product == Product.code",
        backref="recycler_shopping_operation_details",
    )
    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerShoppingOperationDetail.coin_code == Coin.code",
        backref="recycler_shopping_operation_details",
    )
    location = db.relationship(
        "Location",
        primaryjoin="RecyclerShoppingOperationDetail.locations == Location.code",
        backref="recycler_shopping_operation_details",
    )
    recycler_shopping_operation = db.relationship(
        "RecyclerShoppingOperation",
        primaryjoin="RecyclerShoppingOperationDetail.main_correlative == RecyclerShoppingOperation.correlative",
        backref="recycler_shopping_operation_details",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="RecyclerShoppingOperationDetail.store == Store.code",
        backref="recycler_shopping_operation_details",
    )
    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="RecyclerShoppingOperationDetail.unit == ProductsUnit.correlative",
        backref="recycler_shopping_operation_details",
    )


class RecyclerShoppingOperationDetailsLot(RecyclerShoppingOperationDetail):
    __tablename__ = "recycler_shopping_operation_details_lots"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.recycler_shopping_operation_details.main_correlative",
                "public.recycler_shopping_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    lot_number = db.Column(db.String)
    expire = db.Column(db.Boolean)
    expire_date = db.Column(db.Date)
    apply_prices = db.Column(db.Boolean)
    elaboration_date = db.Column(db.Date)
    lot_correlative = db.Column(db.Integer)


class RecyclerShoppingOperationDetailsCoin(db.Model):
    __tablename__ = "recycler_shopping_operation_details_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.recycler_shopping_operation_details.main_correlative",
                "public.recycler_shopping_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    unitary_cost = db.Column(db.Double(53))
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerShoppingOperationDetailsCoin.coin_code == Coin.code",
        backref="recycler_shopping_operation_details_coins",
    )
    recycler_shopping_operation_detail = db.relationship(
        "RecyclerShoppingOperationDetail",
        primaryjoin="and_(RecyclerShoppingOperationDetailsCoin.main_correlative == RecyclerShoppingOperationDetail.main_correlative, RecyclerShoppingOperationDetailsCoin.main_line == RecyclerShoppingOperationDetail.line)",
        backref="recycler_shopping_operation_details_coins",
    )


class RecyclerShoppingOperationDetailsLoad(db.Model):
    __tablename__ = "recycler_shopping_operation_details_load"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["load_correlative", "load_line"],
            [
                "public.recycler_shopping_operation_details.main_correlative",
                "public.recycler_shopping_operation_details.line",
            ],
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.recycler_shopping_operation_details.main_correlative",
                "public.recycler_shopping_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_line = db.Column(db.Integer, primary_key=True)
    load_line = db.Column(db.Integer)
    main_correlative = db.Column(db.Integer)
    load_correlative = db.Column(db.Integer)
    load_amount = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )

    recycler_shopping_operation_detail = db.relationship(
        "RecyclerShoppingOperationDetail",
        primaryjoin="and_(RecyclerShoppingOperationDetailsLoad.load_correlative == RecyclerShoppingOperationDetail.main_correlative, RecyclerShoppingOperationDetailsLoad.load_line == RecyclerShoppingOperationDetail.line)",
        backref="recyclershoppingoperationdetail_recycler_shopping_operation_details_loads",
    )
    recycler_shopping_operation_detail1 = db.relationship(
        "RecyclerShoppingOperationDetail",
        primaryjoin="and_(RecyclerShoppingOperationDetailsLoad.main_correlative == RecyclerShoppingOperationDetail.main_correlative, RecyclerShoppingOperationDetailsLoad.main_line == RecyclerShoppingOperationDetail.line)",
        backref="recyclershoppingoperationdetail_recycler_shopping_operation_details_loads_0",
    )


class RecyclerShoppingOperationDetailsProductsUnit(db.Model):
    __tablename__ = "recycler_shopping_operation_details_products_units"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_line = db.Column(
        db.ForeignKey(
            "public.recycler_shopping_operation_details.line",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_units = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    unitary_cost = db.Column(db.Double(53))
    calculated_cost = db.Column(db.Double(53))
    average_cost = db.Column(db.Double(53))
    perc_waste_cost = db.Column(db.Double(53))
    perc_handling_cost = db.Column(db.Double(53))
    perc_operating_cost = db.Column(db.Double(53))
    perc_additional_cost = db.Column(db.Double(53))
    maximum_price = db.Column(db.Double(53))
    offer_price = db.Column(db.Double(53))
    higher_price = db.Column(db.Double(53))
    minimum_price = db.Column(db.Double(53))
    perc_maximum_price = db.Column(db.Double(53))
    perc_offer_price = db.Column(db.Double(53))
    perc_higher_price = db.Column(db.Double(53))
    perc_minimum_price = db.Column(db.Double(53))
    perc_freight_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    perc_discount_provider = db.Column(db.Double(53), server_default=db.FetchedValue())

    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="RecyclerShoppingOperationDetailsProductsUnit.correlative_units == ProductsUnit.correlative",
        backref="recycler_shopping_operation_details_products_units",
    )
    recycler_shopping_operation_detail = db.relationship(
        "RecyclerShoppingOperationDetail",
        primaryjoin="RecyclerShoppingOperationDetailsProductsUnit.main_line == RecyclerShoppingOperationDetail.line",
        backref="recycler_shopping_operation_details_products_units",
    )


class RecyclerShoppingOperationDetailsSerial(db.Model):
    __tablename__ = "recycler_shopping_operation_details_serials"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.recycler_shopping_operation_details.main_correlative",
                "public.recycler_shopping_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    line = db.Column(db.Integer, primary_key=True, nullable=False)
    serial_no = db.Column(db.String)
    serial_line = db.Column(db.Integer)
    load_by = db.Column(db.Integer)

    recycler_shopping_operation_detail = db.relationship(
        "RecyclerShoppingOperationDetail",
        primaryjoin="and_(RecyclerShoppingOperationDetailsSerial.main_correlative == RecyclerShoppingOperationDetail.main_correlative, RecyclerShoppingOperationDetailsSerial.main_line == RecyclerShoppingOperationDetail.line)",
        backref="recycler_shopping_operation_details_serials",
    )


class RecyclerShoppingOperationTax(db.Model):
    __tablename__ = "recycler_shopping_operation_taxes"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_shopping_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    taxe_code = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    aliquot = db.Column(db.Double(53))
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    line = db.Column(db.Integer, nullable=False)
    tax_type = db.Column(
        db.ForeignKey("public.tax_types.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    recycler_shopping_operation = db.relationship(
        "RecyclerShoppingOperation",
        primaryjoin="RecyclerShoppingOperationTax.main_correlative == RecyclerShoppingOperation.correlative",
        backref="recycler_shopping_operation_taxes",
    )
    tax_type1 = db.relationship(
        "TaxType",
        primaryjoin="RecyclerShoppingOperationTax.tax_type == TaxType.code",
        backref="recycler_shopping_operation_taxes",
    )
    tax1 = db.relationship(
        "Tax",
        primaryjoin="RecyclerShoppingOperationTax.taxe_code == Tax.code",
        backref="recycler_shopping_operation_taxes",
    )


class RecyclerShoppingOperationTaxesCoin(db.Model):
    __tablename__ = "recycler_shopping_operation_taxes_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_taxe_code"],
            [
                "public.recycler_shopping_operation_taxes.main_correlative",
                "public.recycler_shopping_operation_taxes.taxe_code",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_taxe_code = db.Column(db.String, primary_key=True, nullable=False)
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    main_line = db.Column(db.Integer)

    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerShoppingOperationTaxesCoin.coin_code == Coin.code",
        backref="recycler_shopping_operation_taxes_coins",
    )
    recycler_shopping_operation_tax = db.relationship(
        "RecyclerShoppingOperationTax",
        primaryjoin="and_(RecyclerShoppingOperationTaxesCoin.main_correlative == RecyclerShoppingOperationTax.main_correlative, RecyclerShoppingOperationTaxesCoin.main_taxe_code == RecyclerShoppingOperationTax.taxe_code)",
        backref="recycler_shopping_operation_taxes_coins",
    )


class RecyclerWayToPay(db.Model):
    __tablename__ = "recycler_way_to_pay"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(db.Integer, primary_key=True)
    type_operation = db.Column(db.String)
    document_no = db.Column(db.String)
    correlative_related = db.Column(db.Integer)
    module_related = db.Column(db.String)
    total_operation = db.Column(db.Double(53), server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    checks = db.Column(db.Double(53), server_default=db.FetchedValue())
    deposit = db.Column(db.Double(53), server_default=db.FetchedValue())
    transfer = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_card = db.Column(db.Double(53), server_default=db.FetchedValue())
    debit_card = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    generate_advance = db.Column(db.Double(53), server_default=db.FetchedValue())
    advance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    correlative_cash_deposited = db.Column(db.Integer, server_default=db.FetchedValue())
    petty_cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    correlative_advance_generated = db.Column(
        db.Integer, server_default=db.FetchedValue()
    )
    change = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    arching_box_correlative = db.Column(db.Integer, server_default=db.FetchedValue())
    description = db.Column(db.String, server_default=db.FetchedValue())
    bio_payment = db.Column(db.Double(53), server_default=db.FetchedValue())
    movil_payment = db.Column(db.Double(53), server_default=db.FetchedValue())
    courtesy_payment = db.Column(db.Double(53), server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerWayToPay.coin_code == Coin.code",
        backref="recycler_way_to_pays",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="RecyclerWayToPay.station == Station.code",
        backref="recycler_way_to_pays",
    )
    user = db.relationship(
        "User",
        primaryjoin="RecyclerWayToPay.user_code == User.code",
        backref="recycler_way_to_pays",
    )


class RecyclerWayToPayCoin(db.Model):
    __tablename__ = "recycler_way_to_pay_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_way_to_pay.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    factor_type = db.Column(db.Integer)
    way_pay_aliquot = db.Column(db.Double(53))
    total_operation = db.Column(db.Double(53), server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    checks = db.Column(db.Double(53), server_default=db.FetchedValue())
    deposit = db.Column(db.Double(53), server_default=db.FetchedValue())
    transfer = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_card = db.Column(db.Double(53), server_default=db.FetchedValue())
    debit_card = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    generate_advance = db.Column(db.Double(53), server_default=db.FetchedValue())
    advance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    petty_cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    change = db.Column(db.Double(53), server_default=db.FetchedValue())
    bio_payment = db.Column(db.Double(53), server_default=db.FetchedValue())
    movil_payment = db.Column(db.Double(53), server_default=db.FetchedValue())
    courtesy_payment = db.Column(db.Double(53), server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerWayToPayCoin.coin_code == Coin.code",
        backref="recycler_way_to_pay_coins",
    )
    recycler_way_to_pay = db.relationship(
        "RecyclerWayToPay",
        primaryjoin="RecyclerWayToPayCoin.main_correlative == RecyclerWayToPay.correlative",
        backref="recycler_way_to_pay_coins",
    )


class RecyclerWayToPayDetail(db.Model):
    __tablename__ = "recycler_way_to_pay_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.recycler_way_to_pay.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(db.Integer, primary_key=True, nullable=False, unique=True)
    type_operation = db.Column(db.String)
    bank_correlative = db.Column(db.Integer, server_default=db.FetchedValue())
    reference_number = db.Column(db.String)
    amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    card_type = db.Column(
        db.ForeignKey("public.card_types.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    reference_key = db.Column(db.String)
    titular = db.Column(db.String)
    code = db.Column(db.String)
    phone = db.Column(db.String)
    bank = db.Column(
        db.ForeignKey("public.banks.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    emission_date = db.Column(db.Date)
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    bank_account = db.Column(db.String)
    amount_same_bank = db.Column(db.Double(53), server_default=db.FetchedValue())
    amount_other_bank = db.Column(db.Double(53), server_default=db.FetchedValue())
    sale_point = db.Column(
        db.ForeignKey(
            "public.sale_points.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    related_correlative = db.Column(db.Integer, server_default=db.FetchedValue())
    related_module = db.Column(db.String, server_default=db.FetchedValue())
    closing_sales_point_correlative = db.Column(
        db.Integer, server_default=db.FetchedValue()
    )
    petty_cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    amount_local = db.Column(db.Double(53), server_default=db.FetchedValue())

    bank1 = db.relationship(
        "Bank",
        primaryjoin="RecyclerWayToPayDetail.bank == Bank.code",
        backref="recycler_way_to_pay_details",
    )
    card_type1 = db.relationship(
        "CardType",
        primaryjoin="RecyclerWayToPayDetail.card_type == CardType.code",
        backref="recycler_way_to_pay_details",
    )
    coin = db.relationship(
        "Coin",
        primaryjoin="RecyclerWayToPayDetail.coin_code == Coin.code",
        backref="recycler_way_to_pay_details",
    )
    recycler_way_to_pay = db.relationship(
        "RecyclerWayToPay",
        primaryjoin="RecyclerWayToPayDetail.main_correlative == RecyclerWayToPay.correlative",
        backref="recycler_way_to_pay_details",
    )
    sale_point1 = db.relationship(
        "SalePoint",
        primaryjoin="RecyclerWayToPayDetail.sale_point == SalePoint.code",
        backref="recycler_way_to_pay_details",
    )


class RecyclerWayToPayDetailsDet(db.Model):
    __tablename__ = "recycler_way_to_pay_details_det"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.recycler_way_to_pay_details.main_correlative",
                "public.recycler_way_to_pay_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    line = db.Column(db.Integer, primary_key=True, nullable=False)
    type_operation = db.Column(db.String)
    reference_number = db.Column(db.String)
    amount = db.Column(db.Double(53))
    emission_date = db.Column(db.Date)
    account = db.Column(db.String)
    correlative_account = db.Column(db.Integer)

    recycler_way_to_pay_detail = db.relationship(
        "RecyclerWayToPayDetail",
        primaryjoin="and_(RecyclerWayToPayDetailsDet.main_correlative == RecyclerWayToPayDetail.main_correlative, RecyclerWayToPayDetailsDet.main_line == RecyclerWayToPayDetail.line)",
        backref="recycler_way_to_pay_details_dets",
    )


class Report(db.Model):
    __tablename__ = "report"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    title = db.Column(db.String)
    menu = db.Column(
        db.ForeignKey("public.menus.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    report_type = db.Column(db.String, nullable=False, server_default=db.FetchedValue())
    virtualizer = db.Column(db.Boolean, server_default=db.FetchedValue())

    menu1 = db.relationship(
        "Menu", primaryjoin="Report.menu == Menu.code", backref="reports"
    )


class ReportChart(db.Model):
    __tablename__ = "report_charts"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_code", "index_order_display_format", "index_order_query"],
            [
                "public.report_querys.main_code_display_format",
                "public.report_querys.index_order_display_format",
                "public.report_querys.index_order",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    chart_type = db.Column(db.Integer)
    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    main_code = db.Column(db.String)
    index_order_display_format = db.Column(db.Integer)
    index_order_query = db.Column(db.Integer)

    report_query = db.relationship(
        "ReportQuery",
        primaryjoin="and_(ReportChart.main_code == ReportQuery.main_code_display_format, ReportChart.index_order_display_format == ReportQuery.index_order_display_format, ReportChart.index_order_query == ReportQuery.index_order)",
        backref="report_charts",
    )


class ReportChartsCategory(db.Model):
    __tablename__ = "report_charts_categories"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.report_charts.correlative", ondelete="CASCADE", onupdate="CASCADE"
        )
    )
    line = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    index_field = db.Column(db.Integer)

    report_chart = db.relationship(
        "ReportChart",
        primaryjoin="ReportChartsCategory.main_correlative == ReportChart.correlative",
        backref="report_charts_categories",
    )


class ReportChartsSery(db.Model):
    __tablename__ = "report_charts_series"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.report_charts.correlative", ondelete="CASCADE", onupdate="CASCADE"
        )
    )
    line = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    index_field = db.Column(db.Integer)

    report_chart = db.relationship(
        "ReportChart",
        primaryjoin="ReportChartsSery.main_correlative == ReportChart.correlative",
        backref="report_charts_series",
    )


class ReportDisplayFormat(db.Model):
    __tablename__ = "report_display_format"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey("public.report.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    title = db.Column(db.String)
    format = db.Column(db.String)
    index_order = db.Column(db.Integer, primary_key=True, nullable=False)
    visible = db.Column(db.Boolean)
    title_report = db.Column(db.String)
    sub_title_report = db.Column(db.String)
    page_type = db.Column(db.Integer)
    page_orientation = db.Column(db.Integer)
    is_copy = db.Column(db.Boolean, server_default=db.FetchedValue())
    is_copy_selected = db.Column(db.Boolean, server_default=db.FetchedValue())

    report = db.relationship(
        "Report",
        primaryjoin="ReportDisplayFormat.main_code == Report.code",
        backref="report_display_formats",
    )


class ReportField(db.Model):
    __tablename__ = "report_fields"
    __table_args__ = (
        db.ForeignKeyConstraint(
            [
                "main_code_display_format",
                "index_order_display_format",
                "index_order_query",
            ],
            [
                "public.report_querys.main_code_display_format",
                "public.report_querys.index_order_display_format",
                "public.report_querys.index_order",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_code_display_format = db.Column(db.String, primary_key=True, nullable=False)
    index_order_display_format = db.Column(db.Integer, primary_key=True, nullable=False)
    index_order_query = db.Column(db.Integer, primary_key=True, nullable=False)
    index_order = db.Column(db.Integer, primary_key=True, nullable=False)
    code = db.Column(db.String)
    field_label = db.Column(db.String)
    data_type = db.Column(db.String)
    width = db.Column(db.Integer)
    alignment = db.Column(db.Integer, server_default=db.FetchedValue())
    total_type = db.Column(db.Integer, server_default=db.FetchedValue())
    group_by = db.Column(db.Boolean, server_default=db.FetchedValue())
    order_by = db.Column(db.Boolean, server_default=db.FetchedValue())
    group_by_default = db.Column(db.Boolean, server_default=db.FetchedValue())
    order_by_default = db.Column(db.Boolean, server_default=db.FetchedValue())
    field_format = db.Column(db.String, server_default=db.FetchedValue())
    can_be_empty = db.Column(db.Boolean, server_default=db.FetchedValue())
    subreport_parameter = db.Column(db.Boolean, server_default=db.FetchedValue())
    subreport_parameter_order = db.Column(db.Integer, server_default=db.FetchedValue())

    report_query = db.relationship(
        "ReportQuery",
        primaryjoin="and_(ReportField.main_code_display_format == ReportQuery.main_code_display_format, ReportField.index_order_display_format == ReportQuery.index_order_display_format, ReportField.index_order_query == ReportQuery.index_order)",
        backref="report_fields",
    )


class ReportFilter(db.Model):
    __tablename__ = "report_filter"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_code", "main_panel"],
            ["public.report_panel.main_code", "public.report_panel.index_order"],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_code = db.Column(db.String, primary_key=True, nullable=False)
    title = db.Column(db.String)
    index_order = db.Column(db.Integer, primary_key=True, nullable=False)
    filter_type = db.Column(db.String)
    filter_configuration = db.Column(db.String)
    main_panel = db.Column(db.Integer, primary_key=True, nullable=False)
    show_list = db.Column(db.Boolean, server_default=db.FetchedValue())

    report_panel = db.relationship(
        "ReportPanel",
        primaryjoin="and_(ReportFilter.main_code == ReportPanel.main_code, ReportFilter.main_panel == ReportPanel.index_order)",
        backref="report_filters",
    )


class ReportList(db.Model):
    __tablename__ = "report_list"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    browser = db.Column(db.String)
    included = db.Column(db.Boolean)


class ReportListDetail(db.Model):
    __tablename__ = "report_list_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey(
            "public.report_list.code", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    code = db.Column(db.String, primary_key=True, nullable=False)

    report_list = db.relationship(
        "ReportList",
        primaryjoin="ReportListDetail.main_code == ReportList.code",
        backref="report_list_details",
    )


class ReportPanel(db.Model):
    __tablename__ = "report_panel"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey("public.report.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    title = db.Column(db.String)
    index_order = db.Column(db.Integer, primary_key=True, nullable=False)

    report = db.relationship(
        "Report",
        primaryjoin="ReportPanel.main_code == Report.code",
        backref="report_panels",
    )


class ReportParameter(db.Model):
    __tablename__ = "report_parameter"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey("public.report.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    index_order = db.Column(db.Integer, primary_key=True, nullable=False)
    code = db.Column(db.String)
    parameter_type = db.Column(db.String, server_default=db.FetchedValue())
    default_value = db.Column(db.String)

    report = db.relationship(
        "Report",
        primaryjoin="ReportParameter.main_code == Report.code",
        backref="report_parameters",
    )


class ReportQuery(db.Model):
    __tablename__ = "report_querys"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_code_display_format", "index_order_display_format"],
            [
                "public.report_display_format.main_code",
                "public.report_display_format.index_order",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_code_display_format = db.Column(db.String, primary_key=True, nullable=False)
    index_order_display_format = db.Column(db.Integer, primary_key=True, nullable=False)
    index_order = db.Column(db.Integer, primary_key=True, nullable=False)
    query = db.Column(db.String)
    description = db.Column(db.String)
    font_size = db.Column(db.Integer, server_default=db.FetchedValue())
    new_page = db.Column(db.Boolean, server_default=db.FetchedValue())
    preferred_width = db.Column(db.Integer, server_default=db.FetchedValue())
    subreport = db.Column(db.Boolean, server_default=db.FetchedValue())
    main_query = db.Column(db.Integer, server_default=db.FetchedValue())

    report_display_format = db.relationship(
        "ReportDisplayFormat",
        primaryjoin="and_(ReportQuery.main_code_display_format == ReportDisplayFormat.main_code, ReportQuery.index_order_display_format == ReportDisplayFormat.index_order)",
        backref="report_queries",
    )


class RestDetailsComment(db.Model):
    __tablename__ = "rest_details_comments"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    details_group = db.Column(db.String, server_default=db.FetchedValue())


class RestDetailsGroup(db.Model):
    __tablename__ = "rest_details_group"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class RestLocation(db.Model):
    __tablename__ = "rest_location"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class RestTable(db.Model):
    __tablename__ = "rest_table"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    rest_location = db.Column(
        db.ForeignKey(
            "public.rest_location.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    status = db.Column(db.String)

    rest_location1 = db.relationship(
        "RestLocation",
        primaryjoin="RestTable.rest_location == RestLocation.code",
        backref="rest_tables",
    )


class RestTableSale(db.Model):
    __tablename__ = "rest_table_sales"
    __table_args__ = {"schema": "public", "extend_existing": True}

    table_code = db.Column(db.String, primary_key=True, nullable=False)
    correlative_related = db.Column(
        db.ForeignKey(
            "public.sales_operation.correlative",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )

    sales_operation = db.relationship(
        "SalesOperation",
        primaryjoin="RestTableSale.correlative_related == SalesOperation.correlative",
        backref="rest_table_sales",
    )


class RetentionIslrClient(db.Model):
    __tablename__ = "retention_islr_clients"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, unique=True, server_default=db.FetchedValue()
    )
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    reception_date = db.Column(db.Date)
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    client_code = db.Column(db.String)
    client_id = db.Column(db.String)
    client_name = db.Column(db.String)
    client_phone = db.Column(db.String)
    client_address = db.Column(db.String)


class RetentionIslrClientsDetail(db.Model):
    __tablename__ = "retention_islr_clients_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.retention_islr_clients.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    line = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    code_islr = db.Column(
        db.ForeignKey("public.codes_islr.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    calculation_base = db.Column(db.Double(53))
    percent_retention = db.Column(db.Double(53))
    sustraendo = db.Column(db.Double(53))
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    service_description = db.Column(db.String)
    module_related = db.Column(db.String)
    correlative_related = db.Column(db.Integer)
    code_selected = db.Column(db.String)

    codes_islr = db.relationship(
        "CodesIslr",
        primaryjoin="RetentionIslrClientsDetail.code_islr == CodesIslr.code",
        backref="retention_islr_clients_details",
    )
    retention_islr_client = db.relationship(
        "RetentionIslrClient",
        primaryjoin="RetentionIslrClientsDetail.main_correlative == RetentionIslrClient.correlative",
        backref="retention_islr_clients_details",
    )


class RetentionIslrProvider(db.Model):
    __tablename__ = "retention_islr_provider"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    provider_id = db.Column(db.String)
    provider_name = db.Column(db.String)
    provider_phone = db.Column(db.String)
    provider_address = db.Column(db.String)
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    provider_code = db.Column(db.String)


class RetentionIslrProviderDetail(db.Model):
    __tablename__ = "retention_islr_provider_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.retention_islr_provider.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    line = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    code_islr = db.Column(
        db.ForeignKey("public.codes_islr.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    calculation_base = db.Column(db.Double(53))
    percent_retention = db.Column(db.Double(53))
    sustraendo = db.Column(db.Double(53))
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    service_description = db.Column(db.String)
    module_related = db.Column(db.String)
    correlative_related = db.Column(db.Integer)
    code_selected = db.Column(db.String)

    codes_islr = db.relationship(
        "CodesIslr",
        primaryjoin="RetentionIslrProviderDetail.code_islr == CodesIslr.code",
        backref="retention_islr_provider_details",
    )
    retention_islr_provider = db.relationship(
        "RetentionIslrProvider",
        primaryjoin="RetentionIslrProviderDetail.main_correlative == RetentionIslrProvider.correlative",
        backref="retention_islr_provider_details",
    )


class RetentionMunicipalClient(db.Model):
    __tablename__ = "retention_municipal_clients"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, unique=True, server_default=db.FetchedValue()
    )
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    reception_date = db.Column(db.Date)
    percent_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    client_code = db.Column(db.String)
    client_id = db.Column(db.String)
    client_name = db.Column(db.String)
    client_phone = db.Column(db.String)
    client_address = db.Column(db.String)


class RetentionMunicipalClientsDetail(db.Model):
    __tablename__ = "retention_municipal_clients_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.retention_municipal_clients.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    related_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    related_module = db.Column(db.String, primary_key=True, nullable=False)
    line = db.Column(
        db.Integer, nullable=False, unique=True, server_default=db.FetchedValue()
    )
    related_taxes_line = db.Column(db.Integer, primary_key=True, nullable=False)
    total_retention = db.Column(db.Double(53))

    retention_municipal_client = db.relationship(
        "RetentionMunicipalClient",
        primaryjoin="RetentionMunicipalClientsDetail.main_correlative == RetentionMunicipalClient.correlative",
        backref="retention_municipal_clients_details",
    )


class RetentionMunicipalProvider(db.Model):
    __tablename__ = "retention_municipal_provider"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    provider_id = db.Column(db.String)
    provider_name = db.Column(db.String)
    provider_phone = db.Column(db.String)
    provider_address = db.Column(db.String)
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    percent_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    provider_code = db.Column(db.String)


class RetentionMunicipalProviderDetail(db.Model):
    __tablename__ = "retention_municipal_provider_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.retention_municipal_provider.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    related_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    related_module = db.Column(db.String, primary_key=True, nullable=False)
    line = db.Column(
        db.Integer, nullable=False, unique=True, server_default=db.FetchedValue()
    )
    related_taxes_line = db.Column(db.Integer, primary_key=True, nullable=False)
    total_retention = db.Column(db.Double(53))

    retention_municipal_provider = db.relationship(
        "RetentionMunicipalProvider",
        primaryjoin="RetentionMunicipalProviderDetail.main_correlative == RetentionMunicipalProvider.correlative",
        backref="retention_municipal_provider_details",
    )


class RetentionTaxClient(db.Model):
    __tablename__ = "retention_tax_clients"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, unique=True, server_default=db.FetchedValue()
    )
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    reception_date = db.Column(db.Date)
    percent_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    client_code = db.Column(db.String)
    client_id = db.Column(db.String)
    client_name = db.Column(db.String)
    client_phone = db.Column(db.String)
    client_address = db.Column(db.String)


class RetentionTaxClientsDetail(db.Model):
    __tablename__ = "retention_tax_clients_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.retention_tax_clients.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    related_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    related_module = db.Column(db.String, primary_key=True, nullable=False)
    line = db.Column(
        db.Integer, nullable=False, unique=True, server_default=db.FetchedValue()
    )
    related_taxes_line = db.Column(db.Integer, primary_key=True, nullable=False)
    total_retention = db.Column(db.Double(53))

    retention_tax_client = db.relationship(
        "RetentionTaxClient",
        primaryjoin="RetentionTaxClientsDetail.main_correlative == RetentionTaxClient.correlative",
        backref="retention_tax_clients_details",
    )


class RetentionTaxProvider(db.Model):
    __tablename__ = "retention_tax_provider"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, unique=True, server_default=db.FetchedValue()
    )
    correlative_related = db.Column(db.Integer, nullable=False)
    module_related = db.Column(db.String, nullable=False)
    document_no = db.Column(db.String)
    provider_id = db.Column(db.String)
    provider_name = db.Column(db.String)
    provider_phone = db.Column(db.String)
    provider_address = db.Column(db.String)
    emission_date = db.Column(db.Date)
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    percent_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention = db.Column(db.Double(53), server_default=db.FetchedValue())
    provider_code = db.Column(db.String)


class RetentionTaxProviderDetail(db.Model):
    __tablename__ = "retention_tax_provider_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.retention_tax_provider.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    related_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    related_module = db.Column(db.String, primary_key=True, nullable=False)
    line = db.Column(
        db.Integer, nullable=False, unique=True, server_default=db.FetchedValue()
    )
    related_taxes_line = db.Column(db.Integer, primary_key=True, nullable=False)
    total_retention = db.Column(db.Double(53))

    retention_tax_provider = db.relationship(
        "RetentionTaxProvider",
        primaryjoin="RetentionTaxProviderDetail.main_correlative == RetentionTaxProvider.correlative",
        backref="retention_tax_provider_details",
    )


class SalePoint(db.Model):
    __tablename__ = "sale_points"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    bank_account = db.Column(
        db.ForeignKey(
            "public.bank_account.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    biopayment = db.Column(db.Boolean, server_default=db.FetchedValue())

    bank_account1 = db.relationship(
        "BankAccount",
        primaryjoin="SalePoint.bank_account == BankAccount.code",
        backref="sale_points",
    )


class SalePointsDetail(db.Model):
    __tablename__ = "sale_points_detail"
    __table_args__ = {"schema": "public", "extend_existing": True}

    sale_point_code = db.Column(
        db.ForeignKey(
            "public.sale_points.code", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(db.Integer, primary_key=True, nullable=False)
    card_type_code = db.Column(
        db.ForeignKey(
            "public.card_types.code", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    percent_commission = db.Column(db.Double(53))
    percent_above_commission = db.Column(db.Double(53))
    percent_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_exempt_islr = db.Column(db.Double(53), server_default=db.FetchedValue())

    card_type = db.relationship(
        "CardType",
        primaryjoin="SalePointsDetail.card_type_code == CardType.code",
        backref="sale_points_details",
    )
    sale_point = db.relationship(
        "SalePoint",
        primaryjoin="SalePointsDetail.sale_point_code == SalePoint.code",
        backref="sale_points_details",
    )


class SalesDocumentsRel(db.Model):
    __tablename__ = "sales_documents_rel"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, nullable=False, unique=True, server_default=db.FetchedValue()
    )
    main_correlative = db.Column(
        db.ForeignKey(
            "public.sales_operation.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_related = db.Column(db.Integer, primary_key=True, nullable=False)
    module_related = db.Column(db.String, primary_key=True, nullable=False)

    sales_operation = db.relationship(
        "SalesOperation",
        primaryjoin="SalesDocumentsRel.main_correlative == SalesOperation.correlative",
        backref="sales_documents_rels",
    )


class SalesOperation(db.Model):
    __tablename__ = "sales_operation"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    operation_type = db.Column(db.String, index=True)
    document_no = db.Column(db.String, index=True)
    control_no = db.Column(db.String)
    emission_date = db.Column(db.Date, index=True)
    register_hour = db.Column(db.Time)
    register_date = db.Column(db.Date)
    client_code = db.Column(
        db.ForeignKey("public.clients.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    client_name = db.Column(db.String)
    client_id = db.Column(db.String)
    client_address = db.Column(db.String)
    client_phone = db.Column(db.String)
    client_name_fiscal = db.Column(db.Integer)
    seller = db.Column(
        db.ForeignKey("public.sellers.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    credit_days = db.Column(db.Integer)
    expiration_date = db.Column(db.Date)
    wait = db.Column(db.Boolean)
    description = db.Column(db.String)
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    begin_used = db.Column(db.Boolean, server_default=db.FetchedValue())
    total_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_freight = db.Column(db.Double(53), server_default=db.FetchedValue())
    freight = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    operation_comments = db.Column(db.String)
    type_price = db.Column(db.Integer, server_default=db.FetchedValue())
    total_net_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_count_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    pending = db.Column(db.Boolean)
    canceled = db.Column(db.Boolean, nullable=False, server_default=db.FetchedValue())
    freight_tax = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    freight_aliquot = db.Column(db.Double(53))
    total_retention_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention_municipal = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    total_retention_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_operation = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_islr_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_municipal_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    document_no_internal = db.Column(db.String, server_default=db.FetchedValue())
    fiscal_impresion = db.Column(db.Boolean, server_default=db.FetchedValue())
    fiscal_printer_serial = db.Column(db.String, server_default=db.FetchedValue())
    fiscal_printer_z = db.Column(db.String, server_default=db.FetchedValue())
    fiscal_printer_date = db.Column(db.DateTime)
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        index=True,
    )
    sale_point = db.Column(db.Boolean, server_default=db.FetchedValue())
    address_send = db.Column(db.String)
    contact_send = db.Column(db.String)
    phone_send = db.Column(db.String)
    free_tax = db.Column(db.Boolean, server_default=db.FetchedValue())
    delivered = db.Column(db.Boolean, server_default=db.FetchedValue())
    total_weight = db.Column(db.Double(53), server_default=db.FetchedValue())
    restorant = db.Column(db.Boolean, server_default=db.FetchedValue())
    total_exempt = db.Column(db.Double(53), server_default=db.FetchedValue())
    base_igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    shopping_order_document_no = db.Column(db.String, server_default=db.FetchedValue())
    shopping_order_date = db.Column(db.Date)

    client = db.relationship(
        "Client",
        primaryjoin="SalesOperation.client_code == Client.code",
        backref="sales_operations",
    )
    coin = db.relationship(
        "Coin",
        primaryjoin="SalesOperation.coin_code == Coin.code",
        backref="sales_operations",
    )
    tax = db.relationship(
        "Tax",
        primaryjoin="SalesOperation.freight_tax == Tax.code",
        backref="sales_operations",
    )
    location = db.relationship(
        "Location",
        primaryjoin="SalesOperation.locations == Location.code",
        backref="sales_operations",
    )
    seller1 = db.relationship(
        "Seller",
        primaryjoin="SalesOperation.seller == Seller.code",
        backref="sales_operations",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="SalesOperation.station == Station.code",
        backref="sales_operations",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="SalesOperation.store == Store.code",
        backref="sales_operations",
    )
    user = db.relationship(
        "User",
        primaryjoin="SalesOperation.user_code == User.code",
        backref="sales_operations",
    )


class SalesOperationCoin(db.Model):
    __tablename__ = "sales_operation_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.sales_operation.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    factor_type = db.Column(db.Integer)
    buy_aliquot = db.Column(db.Double(53))
    sales_aliquot = db.Column(db.Double(53))
    total_net_details = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_tax_details = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_details = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    discount = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    freight = db.Column(db.Double(53), nullable=False, server_default=db.FetchedValue())
    total_net = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_tax = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total = db.Column(db.Double(53), nullable=False, server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), nullable=False, server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), nullable=False, server_default=db.FetchedValue())
    total_net_cost = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_tax_cost = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_cost = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_operation = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_retention_tax = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_retention_municipal = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_retention_islr = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    retention_tax_prorration = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    retention_islr_prorration = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    retention_municipal_prorration = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    total_exempt = db.Column(db.Double(53), server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin",
        primaryjoin="SalesOperationCoin.coin_code == Coin.code",
        backref="sales_operation_coins",
    )
    sales_operation = db.relationship(
        "SalesOperation",
        primaryjoin="SalesOperationCoin.main_correlative == SalesOperation.correlative",
        backref="sales_operation_coins",
    )


class SalesOperationDetail(db.Model):
    __tablename__ = "sales_operation_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.sales_operation.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        unique=True,
        server_default=db.FetchedValue(),
    )
    code_product = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    description_product = db.Column(db.String)
    referenc = db.Column(db.String)
    mark = db.Column(db.String)
    model = db.Column(db.String)
    amount = db.Column(db.Double(53))
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    unit = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    conversion_factor = db.Column(db.Double(53))
    unit_type = db.Column(db.Integer)
    unitary_cost = db.Column(db.Double(53))
    sale_tax = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    sale_aliquot = db.Column(db.Double(53))
    price = db.Column(db.Double(53), server_default=db.FetchedValue())
    type_price = db.Column(db.Integer, server_default=db.FetchedValue())
    total_net_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    pending_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    buy_tax = db.Column(db.String)
    buy_aliquot = db.Column(db.Double(53))
    update_inventory = db.Column(db.Boolean, server_default=db.FetchedValue())
    amount_released_by_load_order = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    amount_discharged_by_load_delivery_note = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    product_type = db.Column(db.String)
    description = db.Column(db.String)
    technician = db.Column(
        db.ForeignKey(
            "public.technician.code", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        server_default=db.FetchedValue(),
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    total_weight = db.Column(db.Double(53), server_default=db.FetchedValue())

    product = db.relationship(
        "Product",
        primaryjoin="SalesOperationDetail.code_product == Product.code",
        backref="sales_operation_details",
    )
    coin = db.relationship(
        "Coin",
        primaryjoin="SalesOperationDetail.coin_code == Coin.code",
        backref="sales_operation_details",
    )
    location = db.relationship(
        "Location",
        primaryjoin="SalesOperationDetail.locations == Location.code",
        backref="sales_operation_details",
    )
    sales_operation = db.relationship(
        "SalesOperation",
        primaryjoin="SalesOperationDetail.main_correlative == SalesOperation.correlative",
        backref="sales_operation_details",
    )
    tax = db.relationship(
        "Tax",
        primaryjoin="SalesOperationDetail.sale_tax == Tax.code",
        backref="sales_operation_details",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="SalesOperationDetail.store == Store.code",
        backref="sales_operation_details",
    )
    technician1 = db.relationship(
        "Technician",
        primaryjoin="SalesOperationDetail.technician == Technician.code",
        backref="sales_operation_details",
    )
    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="SalesOperationDetail.unit == ProductsUnit.correlative",
        backref="sales_operation_details",
    )


class SalesOperationDetailsLot(SalesOperationDetail):
    __tablename__ = "sales_operation_details_lots"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.sales_operation_details.main_correlative",
                "public.sales_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    lot_number = db.Column(db.String)
    expire = db.Column(db.Boolean)
    expire_date = db.Column(db.Date)
    apply_prices = db.Column(db.Boolean)
    elaboration_date = db.Column(db.Date)
    lot_correlative = db.Column(db.Integer)


class SalesOperationDetailsCoin(db.Model):
    __tablename__ = "sales_operation_details_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.sales_operation_details.main_correlative",
                "public.sales_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    unitary_cost = db.Column(db.Double(53))
    price = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    coin = db.relationship(
        "Coin",
        primaryjoin="SalesOperationDetailsCoin.coin_code == Coin.code",
        backref="sales_operation_details_coins",
    )
    sales_operation_detail = db.relationship(
        "SalesOperationDetail",
        primaryjoin="and_(SalesOperationDetailsCoin.main_correlative == SalesOperationDetail.main_correlative, SalesOperationDetailsCoin.main_line == SalesOperationDetail.line)",
        backref="sales_operation_details_coins",
    )


class SalesOperationDetailsLoad(db.Model):
    __tablename__ = "sales_operation_details_load"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["load_line", "load_correlative"],
            [
                "public.sales_operation_details.line",
                "public.sales_operation_details.main_correlative",
            ],
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        db.ForeignKeyConstraint(
            ["main_line", "main_correlative"],
            [
                "public.sales_operation_details.line",
                "public.sales_operation_details.main_correlative",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_line = db.Column(db.Integer, primary_key=True)
    load_line = db.Column(db.Integer)
    main_correlative = db.Column(db.Integer)
    load_correlative = db.Column(db.Integer)
    load_amount = db.Column(db.Double(53), server_default=db.FetchedValue())

    sales_operation_detail = db.relationship(
        "SalesOperationDetail",
        primaryjoin="and_(SalesOperationDetailsLoad.load_line == SalesOperationDetail.line, SalesOperationDetailsLoad.load_correlative == SalesOperationDetail.main_correlative)",
        backref="salesoperationdetail_sales_operation_details_loads",
    )
    sales_operation_detail1 = db.relationship(
        "SalesOperationDetail",
        primaryjoin="and_(SalesOperationDetailsLoad.main_line == SalesOperationDetail.line, SalesOperationDetailsLoad.main_correlative == SalesOperationDetail.main_correlative)",
        backref="salesoperationdetail_sales_operation_details_loads_0",
    )


class SalesOperationDetailsPart(db.Model):
    __tablename__ = "sales_operation_details_parts"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.sales_operation_details.main_correlative",
                "public.sales_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    line = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        unique=True,
        server_default=db.FetchedValue(),
    )
    code_product = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    description_product = db.Column(db.String)
    referenc = db.Column(db.String)
    mark = db.Column(db.String)
    model = db.Column(db.String)
    show_line = db.Column(db.Boolean)
    part_amount = db.Column(db.Double(53))
    total_amount = db.Column(db.Double(53))
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    unit = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    conversion_factor = db.Column(db.Double(53))
    unit_type = db.Column(db.Integer)
    unitary_cost = db.Column(db.Double(53))
    sale_tax = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    sale_aliquot = db.Column(db.Double(53))
    price = db.Column(db.Double(53), server_default=db.FetchedValue())
    type_price = db.Column(db.Integer, server_default=db.FetchedValue())
    total_net_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    buy_tax = db.Column(db.String)
    buy_aliquot = db.Column(db.Double(53))
    product_type = db.Column(db.String)
    description = db.Column(db.String)
    technician = db.Column(
        db.ForeignKey(
            "public.technician.code", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        server_default=db.FetchedValue(),
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    product = db.relationship(
        "Product",
        primaryjoin="SalesOperationDetailsPart.code_product == Product.code",
        backref="sales_operation_details_parts",
    )
    coin = db.relationship(
        "Coin",
        primaryjoin="SalesOperationDetailsPart.coin_code == Coin.code",
        backref="sales_operation_details_parts",
    )
    location = db.relationship(
        "Location",
        primaryjoin="SalesOperationDetailsPart.locations == Location.code",
        backref="sales_operation_details_parts",
    )
    sales_operation_detail = db.relationship(
        "SalesOperationDetail",
        primaryjoin="and_(SalesOperationDetailsPart.main_correlative == SalesOperationDetail.main_correlative, SalesOperationDetailsPart.main_line == SalesOperationDetail.line)",
        backref="sales_operation_details_parts",
    )
    tax = db.relationship(
        "Tax",
        primaryjoin="SalesOperationDetailsPart.sale_tax == Tax.code",
        backref="sales_operation_details_parts",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="SalesOperationDetailsPart.store == Store.code",
        backref="sales_operation_details_parts",
    )
    technician1 = db.relationship(
        "Technician",
        primaryjoin="SalesOperationDetailsPart.technician == Technician.code",
        backref="sales_operation_details_parts",
    )
    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="SalesOperationDetailsPart.unit == ProductsUnit.correlative",
        backref="sales_operation_details_parts",
    )


class SalesOperationDetailsPartsCoin(db.Model):
    __tablename__ = "sales_operation_details_parts_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line", "main_part_line"],
            [
                "public.sales_operation_details_parts.main_correlative",
                "public.sales_operation_details_parts.main_line",
                "public.sales_operation_details_parts.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    main_part_line = db.Column(db.Integer, primary_key=True, nullable=False)
    unitary_cost = db.Column(db.Double(53))
    price = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    coin = db.relationship(
        "Coin",
        primaryjoin="SalesOperationDetailsPartsCoin.coin_code == Coin.code",
        backref="sales_operation_details_parts_coins",
    )
    sales_operation_details_part = db.relationship(
        "SalesOperationDetailsPart",
        primaryjoin="and_(SalesOperationDetailsPartsCoin.main_correlative == SalesOperationDetailsPart.main_correlative, SalesOperationDetailsPartsCoin.main_line == SalesOperationDetailsPart.main_line, SalesOperationDetailsPartsCoin.main_part_line == SalesOperationDetailsPart.line)",
        backref="sales_operation_details_parts_coins",
    )


class SalesOperationDetailsSerial(db.Model):
    __tablename__ = "sales_operation_details_serials"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.sales_operation_details.main_correlative",
                "public.sales_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    serial_no = db.Column(db.String)
    serial_line = db.Column(db.Integer)
    load_by = db.Column(db.Integer)

    sales_operation_detail = db.relationship(
        "SalesOperationDetail",
        primaryjoin="and_(SalesOperationDetailsSerial.main_correlative == SalesOperationDetail.main_correlative, SalesOperationDetailsSerial.main_line == SalesOperationDetail.line)",
        backref="sales_operation_details_serials",
    )


class SalesOperationTax(db.Model):
    __tablename__ = "sales_operation_taxes"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.sales_operation.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    taxe_code = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    aliquot = db.Column(db.Double(53))
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    line = db.Column(db.Integer, nullable=False, server_default=db.FetchedValue())
    tax_type = db.Column(db.ForeignKey("public.tax_types.code", onupdate="CASCADE"))

    sales_operation = db.relationship(
        "SalesOperation",
        primaryjoin="SalesOperationTax.main_correlative == SalesOperation.correlative",
        backref="sales_operation_taxes",
    )
    tax_type1 = db.relationship(
        "TaxType",
        primaryjoin="SalesOperationTax.tax_type == TaxType.code",
        backref="sales_operation_taxes",
    )
    tax1 = db.relationship(
        "Tax",
        primaryjoin="SalesOperationTax.taxe_code == Tax.code",
        backref="sales_operation_taxes",
    )


class SalesOperationTaxesCoin(db.Model):
    __tablename__ = "sales_operation_taxes_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_taxe_code"],
            [
                "public.sales_operation_taxes.main_correlative",
                "public.sales_operation_taxes.taxe_code",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_taxe_code = db.Column(db.String, primary_key=True, nullable=False)
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    main_line = db.Column(db.Integer)

    coin = db.relationship(
        "Coin",
        primaryjoin="SalesOperationTaxesCoin.coin_code == Coin.code",
        backref="sales_operation_taxes_coins",
    )
    sales_operation_tax = db.relationship(
        "SalesOperationTax",
        primaryjoin="and_(SalesOperationTaxesCoin.main_correlative == SalesOperationTax.main_correlative, SalesOperationTaxesCoin.main_taxe_code == SalesOperationTax.taxe_code)",
        backref="sales_operation_taxes_coins",
    )


class Seller(db.Model):
    __tablename__ = "sellers"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    status = db.Column(
        db.ForeignKey("public.status.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    percent_sales = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    percent_receivable = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    inkeeper = db.Column(db.Boolean, server_default=db.FetchedValue())
    user_code = db.Column(db.String)
    percent_gerencial_debit_note = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percent_gerencial_credit_note = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percent_returned_check = db.Column(db.Double(53), server_default=db.FetchedValue())

    status1 = db.relationship(
        "Status", primaryjoin="Seller.status == Status.code", backref="sellers"
    )


class SellersRangeCommission(db.Model):
    __tablename__ = "sellers_range_commissions"
    __table_args__ = {"schema": "public", "extend_existing": True}

    seller_code = db.Column(
        db.ForeignKey("public.sellers.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    type_comissions = db.Column(db.String, primary_key=True, nullable=False)
    order_no = db.Column(db.Integer, primary_key=True, nullable=False)
    initial_range = db.Column(db.Double(53))
    final_range = db.Column(db.Double(53))
    value_range = db.Column(db.Double(53))

    seller = db.relationship(
        "Seller",
        primaryjoin="SellersRangeCommission.seller_code == Seller.code",
        backref="sellers_range_commissions",
    )


class ShoppingDocumentsRel(db.Model):
    __tablename__ = "shopping_documents_rel"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, nullable=False, unique=True, server_default=db.FetchedValue()
    )
    main_correlative = db.Column(
        db.ForeignKey(
            "public.shopping_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_related = db.Column(db.Integer, primary_key=True, nullable=False)
    module_related = db.Column(db.String, primary_key=True, nullable=False)

    shopping_operation = db.relationship(
        "ShoppingOperation",
        primaryjoin="ShoppingDocumentsRel.main_correlative == ShoppingOperation.correlative",
        backref="shopping_documents_rels",
    )


class ShoppingOperation(db.Model):
    __tablename__ = "shopping_operation"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    operation_type = db.Column(db.String)
    document_no = db.Column(db.String)
    control_no = db.Column(db.String)
    emission_date = db.Column(db.Date)
    reception_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    register_date = db.Column(db.Date)
    provider_code = db.Column(
        db.ForeignKey("public.provider.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    provider_name = db.Column(db.String)
    provider_id = db.Column(db.String)
    provider_address = db.Column(db.String)
    provider_phone = db.Column(db.String)
    credit_days = db.Column(db.Integer)
    expiration_date = db.Column(db.Date)
    wait = db.Column(db.Boolean)
    description = db.Column(db.String)
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    begin_used = db.Column(db.Boolean, server_default=db.FetchedValue())
    total_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_freight = db.Column(db.Double(53), server_default=db.FetchedValue())
    freight = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    operation_comments = db.Column(db.String)
    total_count_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    pending = db.Column(db.Boolean)
    buyer = db.Column(db.String)
    freight_tax = db.Column(db.String)
    freight_aliquot = db.Column(db.Double(53))
    total_retention_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention_municipal = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    total_retention_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_operation = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_islr_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_municipal_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    free_tax = db.Column(db.Boolean, nullable=False, server_default=db.FetchedValue())
    total_exempt = db.Column(db.Double(53), server_default=db.FetchedValue())
    secondary_coin = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    base_igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    igtf = db.Column(db.Double(53), server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin",
        primaryjoin="ShoppingOperation.coin_code == Coin.code",
        backref="coin_shopping_operations",
    )
    location = db.relationship(
        "Location",
        primaryjoin="ShoppingOperation.locations == Location.code",
        backref="shopping_operations",
    )
    provider = db.relationship(
        "Provider",
        primaryjoin="ShoppingOperation.provider_code == Provider.code",
        backref="shopping_operations",
    )
    coin1 = db.relationship(
        "Coin",
        primaryjoin="ShoppingOperation.secondary_coin == Coin.code",
        backref="coin_shopping_operations_0",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="ShoppingOperation.station == Station.code",
        backref="shopping_operations",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="ShoppingOperation.store == Store.code",
        backref="shopping_operations",
    )
    user = db.relationship(
        "User",
        primaryjoin="ShoppingOperation.user_code == User.code",
        backref="shopping_operations",
    )
    cond_receipt = db.relationship(
        "CondReceipt", secondary="cond_receipt_details", backref="shopping_operations"
    )


class CondShoppingOperation(ShoppingOperation):
    __tablename__ = "cond_shopping_operation"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.shopping_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    concept_code = db.Column(
        db.ForeignKey(
            "public.cond_concept.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    property_code = db.Column(
        db.ForeignKey("public.clients.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    concept_description = db.Column(db.String, server_default=db.FetchedValue())

    cond_concept = db.relationship(
        "CondConcept",
        primaryjoin="CondShoppingOperation.concept_code == CondConcept.code",
        backref="cond_shopping_operations",
    )
    client = db.relationship(
        "Client",
        primaryjoin="CondShoppingOperation.property_code == Client.code",
        backref="cond_shopping_operations",
    )


class ShoppingOperationCoin(db.Model):
    __tablename__ = "shopping_operation_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.shopping_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    factor_type = db.Column(db.Integer)
    buy_aliquot = db.Column(db.Double(53))
    sales_aliquot = db.Column(db.Double(53))
    total_net_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_details = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    freight = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_retention_municipal = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    total_retention_islr = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_operation = db.Column(db.Double(53), server_default=db.FetchedValue())
    retention_tax_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_islr_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    retention_municipal_prorration = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    total_exempt = db.Column(db.Double(53), server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin",
        primaryjoin="ShoppingOperationCoin.coin_code == Coin.code",
        backref="shopping_operation_coins",
    )
    shopping_operation = db.relationship(
        "ShoppingOperation",
        primaryjoin="ShoppingOperationCoin.main_correlative == ShoppingOperation.correlative",
        backref="shopping_operation_coins",
    )


class ShoppingOperationDetail(db.Model):
    __tablename__ = "shopping_operation_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.shopping_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        unique=True,
        server_default=db.FetchedValue(),
    )
    code_product = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    description_product = db.Column(db.String)
    referenc = db.Column(db.String)
    mark = db.Column(db.String)
    model = db.Column(db.String)
    amount = db.Column(db.Double(53))
    store = db.Column(
        db.ForeignKey("public.store.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locations = db.Column(
        db.ForeignKey("public.locations.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    unit = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    conversion_factor = db.Column(db.Double(53))
    unit_type = db.Column(db.Integer)
    unitary_cost = db.Column(db.Double(53))
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    pending_amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    buy_tax = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    buy_aliquot = db.Column(db.Double(53))
    update_inventory = db.Column(db.Boolean, server_default=db.FetchedValue())
    amount_released_by_load_order = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    amount_charged_by_load_delivery_note = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    product_type = db.Column(db.String)
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    change_price = db.Column(db.Boolean, server_default=db.FetchedValue())

    tax = db.relationship(
        "Tax",
        primaryjoin="ShoppingOperationDetail.buy_tax == Tax.code",
        backref="shopping_operation_details",
    )
    product = db.relationship(
        "Product",
        primaryjoin="ShoppingOperationDetail.code_product == Product.code",
        backref="shopping_operation_details",
    )
    coin = db.relationship(
        "Coin",
        primaryjoin="ShoppingOperationDetail.coin_code == Coin.code",
        backref="shopping_operation_details",
    )
    location = db.relationship(
        "Location",
        primaryjoin="ShoppingOperationDetail.locations == Location.code",
        backref="shopping_operation_details",
    )
    shopping_operation = db.relationship(
        "ShoppingOperation",
        primaryjoin="ShoppingOperationDetail.main_correlative == ShoppingOperation.correlative",
        backref="shopping_operation_details",
    )
    store1 = db.relationship(
        "Store",
        primaryjoin="ShoppingOperationDetail.store == Store.code",
        backref="shopping_operation_details",
    )
    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="ShoppingOperationDetail.unit == ProductsUnit.correlative",
        backref="shopping_operation_details",
    )


class ShoppingOperationDetailsLot(ShoppingOperationDetail):
    __tablename__ = "shopping_operation_details_lots"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.shopping_operation_details.main_correlative",
                "public.shopping_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    lot_number = db.Column(db.String)
    expire = db.Column(db.Boolean)
    expire_date = db.Column(db.Date)
    apply_prices = db.Column(db.Boolean)
    elaboration_date = db.Column(db.Date)
    lot_correlative = db.Column(db.Integer)


class ShoppingOperationDetailsCoin(db.Model):
    __tablename__ = "shopping_operation_details_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.shopping_operation_details.main_correlative",
                "public.shopping_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    unitary_cost = db.Column(db.Double(53))
    total_net_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_gross = db.Column(db.Double(53), server_default=db.FetchedValue())
    discount = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_net = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_tax = db.Column(db.Double(53), server_default=db.FetchedValue())
    total = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    coin = db.relationship(
        "Coin",
        primaryjoin="ShoppingOperationDetailsCoin.coin_code == Coin.code",
        backref="shopping_operation_details_coins",
    )
    shopping_operation_detail = db.relationship(
        "ShoppingOperationDetail",
        primaryjoin="and_(ShoppingOperationDetailsCoin.main_correlative == ShoppingOperationDetail.main_correlative, ShoppingOperationDetailsCoin.main_line == ShoppingOperationDetail.line)",
        backref="shopping_operation_details_coins",
    )


class ShoppingOperationDetailsLoad(db.Model):
    __tablename__ = "shopping_operation_details_load"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["load_correlative", "load_line"],
            [
                "public.shopping_operation_details.main_correlative",
                "public.shopping_operation_details.line",
            ],
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.shopping_operation_details.main_correlative",
                "public.shopping_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_line = db.Column(db.Integer, primary_key=True)
    load_line = db.Column(db.Integer)
    main_correlative = db.Column(db.Integer)
    load_correlative = db.Column(db.Integer)
    load_amount = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )

    shopping_operation_detail = db.relationship(
        "ShoppingOperationDetail",
        primaryjoin="and_(ShoppingOperationDetailsLoad.load_correlative == ShoppingOperationDetail.main_correlative, ShoppingOperationDetailsLoad.load_line == ShoppingOperationDetail.line)",
        backref="shoppingoperationdetail_shopping_operation_details_loads",
    )
    shopping_operation_detail1 = db.relationship(
        "ShoppingOperationDetail",
        primaryjoin="and_(ShoppingOperationDetailsLoad.main_correlative == ShoppingOperationDetail.main_correlative, ShoppingOperationDetailsLoad.main_line == ShoppingOperationDetail.line)",
        backref="shoppingoperationdetail_shopping_operation_details_loads_0",
    )


class ShoppingOperationDetailsProductsUnit(db.Model):
    __tablename__ = "shopping_operation_details_products_units"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_line = db.Column(
        db.ForeignKey(
            "public.shopping_operation_details.line",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_units = db.Column(
        db.ForeignKey(
            "public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    unitary_cost = db.Column(db.Double(53))
    calculated_cost = db.Column(db.Double(53))
    average_cost = db.Column(db.Double(53))
    perc_waste_cost = db.Column(db.Double(53))
    perc_handling_cost = db.Column(db.Double(53))
    perc_operating_cost = db.Column(db.Double(53))
    perc_additional_cost = db.Column(db.Double(53))
    maximum_price = db.Column(db.Double(53))
    offer_price = db.Column(db.Double(53))
    higher_price = db.Column(db.Double(53))
    minimum_price = db.Column(db.Double(53))
    perc_maximum_price = db.Column(db.Double(53))
    perc_offer_price = db.Column(db.Double(53))
    perc_higher_price = db.Column(db.Double(53))
    perc_minimum_price = db.Column(db.Double(53))
    perc_freight_cost = db.Column(db.Double(53), server_default=db.FetchedValue())
    perc_discount_provider = db.Column(db.Double(53), server_default=db.FetchedValue())

    products_unit = db.relationship(
        "ProductsUnit",
        primaryjoin="ShoppingOperationDetailsProductsUnit.correlative_units == ProductsUnit.correlative",
        backref="shopping_operation_details_products_units",
    )
    shopping_operation_detail = db.relationship(
        "ShoppingOperationDetail",
        primaryjoin="ShoppingOperationDetailsProductsUnit.main_line == ShoppingOperationDetail.line",
        backref="shopping_operation_details_products_units",
    )


class ShoppingOperationDetailsSerial(db.Model):
    __tablename__ = "shopping_operation_details_serials"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.shopping_operation_details.main_correlative",
                "public.shopping_operation_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    serial_no = db.Column(db.String)
    serial_line = db.Column(db.Integer)
    load_by = db.Column(db.Integer)

    shopping_operation_detail = db.relationship(
        "ShoppingOperationDetail",
        primaryjoin="and_(ShoppingOperationDetailsSerial.main_correlative == ShoppingOperationDetail.main_correlative, ShoppingOperationDetailsSerial.main_line == ShoppingOperationDetail.line)",
        backref="shopping_operation_details_serials",
    )


class ShoppingOperationTax(db.Model):
    __tablename__ = "shopping_operation_taxes"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.shopping_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    taxe_code = db.Column(
        db.ForeignKey("public.taxes.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    aliquot = db.Column(db.Double(53))
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    line = db.Column(db.Integer, nullable=False, server_default=db.FetchedValue())
    tax_type = db.Column(
        db.ForeignKey("public.tax_types.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    shopping_operation = db.relationship(
        "ShoppingOperation",
        primaryjoin="ShoppingOperationTax.main_correlative == ShoppingOperation.correlative",
        backref="shopping_operation_taxes",
    )
    tax_type1 = db.relationship(
        "TaxType",
        primaryjoin="ShoppingOperationTax.tax_type == TaxType.code",
        backref="shopping_operation_taxes",
    )
    tax1 = db.relationship(
        "Tax",
        primaryjoin="ShoppingOperationTax.taxe_code == Tax.code",
        backref="shopping_operation_taxes",
    )


class ShoppingOperationTaxesCoin(db.Model):
    __tablename__ = "shopping_operation_taxes_coins"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_taxe_code"],
            [
                "public.shopping_operation_taxes.main_correlative",
                "public.shopping_operation_taxes.taxe_code",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_taxe_code = db.Column(db.String, primary_key=True, nullable=False)
    taxable = db.Column(db.Double(53))
    tax = db.Column(db.Double(53))
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    main_line = db.Column(db.Integer)

    coin = db.relationship(
        "Coin",
        primaryjoin="ShoppingOperationTaxesCoin.coin_code == Coin.code",
        backref="shopping_operation_taxes_coins",
    )
    shopping_operation_tax = db.relationship(
        "ShoppingOperationTax",
        primaryjoin="and_(ShoppingOperationTaxesCoin.main_correlative == ShoppingOperationTax.main_correlative, ShoppingOperationTaxesCoin.main_taxe_code == ShoppingOperationTax.taxe_code)",
        backref="shopping_operation_taxes_coins",
    )


class Size(db.Model):
    __tablename__ = "sizes"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class Station(db.Model):
    __tablename__ = "stations"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    numeration_sales_bill = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    sale_point = db.Column(
        db.ForeignKey(
            "public.sale_points.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    tactile = db.Column(db.Boolean, server_default=db.FetchedValue())
    show_browser_external_mode = db.Column(db.Boolean, server_default=db.FetchedValue())
    use_sale_point_numeration = db.Column(db.Boolean, server_default=db.FetchedValue())
    numeration_sales_point_bill = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    fiscal_contingency = db.Column(db.Boolean, server_default=db.FetchedValue())
    use_arching_box = db.Column(db.Boolean, server_default=db.FetchedValue())
    numeration_income = db.Column(db.String, server_default=db.FetchedValue())
    bio_sale_point = db.Column(
        db.ForeignKey(
            "public.sale_points.code", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        server_default=db.FetchedValue(),
    )
    sale_document_type = db.Column(db.Integer, server_default=db.FetchedValue())

    sale_point1 = db.relationship(
        "SalePoint",
        primaryjoin="Station.bio_sale_point == SalePoint.code",
        backref="salepoint_stations",
    )
    sale_point2 = db.relationship(
        "SalePoint",
        primaryjoin="Station.sale_point == SalePoint.code",
        backref="salepoint_stations_0",
    )


class DataCollectorConfig(Station):
    __tablename__ = "data_collector_config"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, nullable=False, unique=True, server_default=db.FetchedValue()
    )
    station_code = db.Column(
        db.ForeignKey("public.stations.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    model = db.Column(db.String)
    port = db.Column(db.String)
    baudrate = db.Column(db.Integer)


class ScaleConfig(Station):
    __tablename__ = "scale_config"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, nullable=False, unique=True, server_default=db.FetchedValue()
    )
    station_code = db.Column(
        db.ForeignKey("public.stations.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    scale_model = db.Column(db.String)
    port = db.Column(db.String)


class StationsCommand(db.Model):
    __tablename__ = "stations_command"
    __table_args__ = {"schema": "public", "extend_existing": True}

    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    command = db.Column(
        db.ForeignKey("public.command.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    printer = db.Column(db.String)
    line = db.Column(db.Integer, nullable=False, server_default=db.FetchedValue())

    command1 = db.relationship(
        "Command",
        primaryjoin="StationsCommand.command == Command.code",
        backref="stations_commands",
    )
    station1 = db.relationship(
        "Station",
        primaryjoin="StationsCommand.station == Station.code",
        backref="stations_commands",
    )


class StationsSalesPoint(db.Model):
    __tablename__ = "stations_sales_point"
    __table_args__ = {"schema": "public", "extend_existing": True}

    id = db.Column(db.Integer, primary_key=True, server_default=db.FetchedValue())
    station_code = db.Column(
        db.ForeignKey("public.stations.code", ondelete="CASCADE", onupdate="CASCADE")
    )
    sale_point_code = db.Column(
        db.ForeignKey(
            "public.sale_points.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )

    sale_point = db.relationship(
        "SalePoint",
        primaryjoin="StationsSalesPoint.sale_point_code == SalePoint.code",
        backref="stations_sales_points",
    )
    station = db.relationship(
        "Station",
        primaryjoin="StationsSalesPoint.station_code == Station.code",
        backref="stations_sales_points",
    )


class Status(db.Model):
    __tablename__ = "status"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    internal_use = db.Column(db.Boolean)


class Store(db.Model):
    __tablename__ = "store"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class SystemProperty(db.Model):
    __tablename__ = "system_properties"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.Integer, primary_key=True, nullable=False)
    properties_group = db.Column(
        db.ForeignKey(
            "public.properties_group.code", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    profile = db.Column(
        db.ForeignKey("public.profile.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    description = db.Column(db.String)
    system_value = db.Column(db.String)
    system_configuration = db.Column(db.String)
    default_value = db.Column(db.String)

    profile1 = db.relationship(
        "Profile",
        primaryjoin="SystemProperty.profile == Profile.code",
        backref="system_properties",
    )
    properties_group1 = db.relationship(
        "PropertiesGroup",
        primaryjoin="SystemProperty.properties_group == PropertiesGroup.code",
        backref="system_properties",
    )


class SystemVersion(db.Model):
    __tablename__ = "system_version"
    __table_args__ = {"schema": "public", "extend_existing": True}

    system_version = db.Column(db.String, primary_key=True)


class TaxType(db.Model):
    __tablename__ = "tax_types"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String)
    fiscal_printer_position = db.Column(db.Integer)
    status = db.Column(db.Boolean, server_default=db.FetchedValue())


class Tax(db.Model):
    __tablename__ = "taxes"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    aliquot = db.Column(db.Double(53))
    short_description = db.Column(db.String)
    line = db.Column(db.ForeignKey("public.tax_types.code"), nullable=False)
    status = db.Column(db.Boolean, server_default=db.FetchedValue())

    tax_type = db.relationship(
        "TaxType", primaryjoin="Tax.line == TaxType.code", backref="taxes"
    )


class Technician(db.Model):
    __tablename__ = "technician"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    status = db.Column(
        db.ForeignKey("public.status.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    percent_commission_maximum_price = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percent_commission_offer_price = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percent_commission_higher_price = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percent_commission_minimum_price = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )
    percent_commission_variable_price = db.Column(
        db.Double(53), server_default=db.FetchedValue()
    )

    status1 = db.relationship(
        "Status", primaryjoin="Technician.status == Status.code", backref="technicians"
    )


class Town(db.Model):
    __tablename__ = "towns"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class Unit(db.Model):
    __tablename__ = "units"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class User(db.Model, UserMixin):
    __tablename__ = "users"
    __table_args__ = {"schema": "public", "extend_existing": True}

    def get_id(self):
        return str(self.code)

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    status = db.Column(
        db.ForeignKey("public.status.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    email = db.Column(db.String)
    profile = db.Column(
        db.ForeignKey("public.profile.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    user_password = db.Column(db.String)
    security_question = db.Column(db.String)
    answer = db.Column(db.String)
    display_screen = db.Column(db.Boolean, server_default=db.FetchedValue())
    change_password = db.Column(db.Boolean, server_default=db.FetchedValue())
    company_email = db.Column(
        db.ForeignKey("public.emails.account", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        server_default=db.FetchedValue(),
    )
    allow_change_password = db.Column(db.Boolean, server_default=db.FetchedValue())
    allow_store_password = db.Column(db.Boolean, server_default=db.FetchedValue())
    technician = db.Column(db.String, server_default=db.FetchedValue())
    security_code = db.Column(db.String, server_default=db.FetchedValue())
    user_image = db.Column(db.LargeBinary)
    image_type = db.Column(db.String, server_default=db.FetchedValue())

    email1 = db.relationship(
        "Email", primaryjoin="User.company_email == Email.account", backref="users"
    )
    profile1 = db.relationship(
        "Profile", primaryjoin="User.profile == Profile.code", backref="users"
    )
    status1 = db.relationship(
        "Status", primaryjoin="User.status == Status.code", backref="users"
    )


class Vehicle(db.Model):
    __tablename__ = "vehicles"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    maximum_capacity = db.Column(db.Double(53))


class WayToPay(db.Model):
    __tablename__ = "way_to_pay"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    type_operation = db.Column(db.String)
    document_no = db.Column(db.String)
    correlative_related = db.Column(db.Integer)
    module_related = db.Column(db.String)
    total_operation = db.Column(db.Double(53), server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    checks = db.Column(db.Double(53), server_default=db.FetchedValue())
    deposit = db.Column(db.Double(53), server_default=db.FetchedValue())
    transfer = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_card = db.Column(db.Double(53), server_default=db.FetchedValue())
    debit_card = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    generate_advance = db.Column(db.Double(53), server_default=db.FetchedValue())
    advance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    register_date = db.Column(db.Date)
    register_hour = db.Column(db.Time)
    correlative_cash_deposited = db.Column(db.Integer, server_default=db.FetchedValue())
    petty_cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    correlative_advance_generated = db.Column(
        db.Integer, server_default=db.FetchedValue()
    )
    change = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    arching_box_correlative = db.Column(db.Integer, server_default=db.FetchedValue())
    description = db.Column(db.String, server_default=db.FetchedValue())
    bio_payment = db.Column(db.Double(53), server_default=db.FetchedValue())
    movil_payment = db.Column(db.Double(53), server_default=db.FetchedValue())
    courtesy_payment = db.Column(db.Double(53), server_default=db.FetchedValue())
    apply_igtf = db.Column(db.Boolean, server_default=db.FetchedValue())
    payment_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    base_igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    percent_igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    igtf = db.Column(db.Double(53), server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin", primaryjoin="WayToPay.coin_code == Coin.code", backref="way_to_pays"
    )
    station1 = db.relationship(
        "Station", primaryjoin="WayToPay.station == Station.code", backref="way_to_pays"
    )
    user = db.relationship(
        "User", primaryjoin="WayToPay.user_code == User.code", backref="way_to_pays"
    )


class WayToPayCoin(db.Model):
    __tablename__ = "way_to_pay_coins"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.way_to_pay.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    factor_type = db.Column(db.Integer)
    way_pay_aliquot = db.Column(db.Double(53))
    total_operation = db.Column(db.Double(53), server_default=db.FetchedValue())
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    checks = db.Column(db.Double(53), server_default=db.FetchedValue())
    deposit = db.Column(db.Double(53), server_default=db.FetchedValue())
    transfer = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_card = db.Column(db.Double(53), server_default=db.FetchedValue())
    debit_card = db.Column(db.Double(53), server_default=db.FetchedValue())
    total_credit = db.Column(db.Double(53), server_default=db.FetchedValue())
    generate_advance = db.Column(db.Double(53), server_default=db.FetchedValue())
    advance_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    credit_note_applied = db.Column(db.Double(53), server_default=db.FetchedValue())
    petty_cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    change = db.Column(db.Double(53), server_default=db.FetchedValue())
    bio_payment = db.Column(db.Double(53), server_default=db.FetchedValue())
    movil_payment = db.Column(db.Double(53), server_default=db.FetchedValue())
    courtesy_payment = db.Column(db.Double(53), server_default=db.FetchedValue())
    payment_applied = db.Column(db.Double(53), server_default=db.FetchedValue())

    coin = db.relationship(
        "Coin",
        primaryjoin="WayToPayCoin.coin_code == Coin.code",
        backref="way_to_pay_coins",
    )
    way_to_pay = db.relationship(
        "WayToPay",
        primaryjoin="WayToPayCoin.main_correlative == WayToPay.correlative",
        backref="way_to_pay_coins",
    )


class WayToPayDetail(db.Model):
    __tablename__ = "way_to_pay_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.way_to_pay.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        unique=True,
        server_default=db.FetchedValue(),
    )
    type_operation = db.Column(db.String)
    bank_correlative = db.Column(db.Integer, server_default=db.FetchedValue())
    reference_number = db.Column(db.String)
    amount = db.Column(db.Double(53), server_default=db.FetchedValue())
    card_type = db.Column(
        db.ForeignKey("public.card_types.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    reference_key = db.Column(db.String)
    titular = db.Column(db.String)
    code = db.Column(db.String)
    phone = db.Column(db.String)
    bank = db.Column(
        db.ForeignKey("public.banks.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    emission_date = db.Column(db.Date)
    cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    bank_account = db.Column(db.String)
    amount_same_bank = db.Column(db.Double(53), server_default=db.FetchedValue())
    amount_other_bank = db.Column(db.Double(53), server_default=db.FetchedValue())
    sale_point = db.Column(
        db.ForeignKey(
            "public.sale_points.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    related_correlative = db.Column(db.Integer, server_default=db.FetchedValue())
    related_module = db.Column(db.String, server_default=db.FetchedValue())
    closing_sales_point_correlative = db.Column(
        db.Integer, server_default=db.FetchedValue()
    )
    petty_cash = db.Column(db.Double(53), server_default=db.FetchedValue())
    coin_code = db.Column(
        db.ForeignKey("public.coin.code", ondelete="RESTRICT", onupdate="CASCADE"),
        server_default=db.FetchedValue(),
    )
    amount_local = db.Column(db.Double(53), server_default=db.FetchedValue())
    apply_igtf = db.Column(db.Boolean, server_default=db.FetchedValue())
    igtf = db.Column(db.Double(53), server_default=db.FetchedValue())
    base_igtf = db.Column(db.Double(53), server_default=db.FetchedValue())

    bank1 = db.relationship(
        "Bank",
        primaryjoin="WayToPayDetail.bank == Bank.code",
        backref="way_to_pay_details",
    )
    card_type1 = db.relationship(
        "CardType",
        primaryjoin="WayToPayDetail.card_type == CardType.code",
        backref="way_to_pay_details",
    )
    coin = db.relationship(
        "Coin",
        primaryjoin="WayToPayDetail.coin_code == Coin.code",
        backref="way_to_pay_details",
    )
    way_to_pay = db.relationship(
        "WayToPay",
        primaryjoin="WayToPayDetail.main_correlative == WayToPay.correlative",
        backref="way_to_pay_details",
    )
    sale_point1 = db.relationship(
        "SalePoint",
        primaryjoin="WayToPayDetail.sale_point == SalePoint.code",
        backref="way_to_pay_details",
    )
    closing_sales_point = db.relationship(
        "ClosingSalesPoint",
        secondary="closing_sales_point_way_to_pay",
        backref="way_to_pay_details",
    )


class WayToPayDetailsDet(db.Model):
    __tablename__ = "way_to_pay_details_det"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["main_correlative", "main_line"],
            [
                "public.way_to_pay_details.main_correlative",
                "public.way_to_pay_details.line",
            ],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        {"schema": "public", "extend_existing": True},
    )

    main_correlative = db.Column(db.Integer, primary_key=True, nullable=False)
    main_line = db.Column(db.Integer, primary_key=True, nullable=False)
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    type_operation = db.Column(db.String)
    reference_number = db.Column(db.String)
    amount = db.Column(db.Double(53))
    emission_date = db.Column(db.Date)
    account = db.Column(db.String)
    correlative_account = db.Column(db.Integer)

    way_to_pay_detail = db.relationship(
        "WayToPayDetail",
        primaryjoin="and_(WayToPayDetailsDet.main_correlative == WayToPayDetail.main_correlative, WayToPayDetailsDet.main_line == WayToPayDetail.line)",
        backref="way_to_pay_details_dets",
    )


class Workshop(db.Model):
    __tablename__ = "workshop"
    __table_args__ = {"schema": "public", "extend_existing": True}

    correlative = db.Column(
        db.Integer, primary_key=True, server_default=db.FetchedValue()
    )
    emission_date = db.Column(db.Date)
    document_no = db.Column(db.String)
    department = db.Column(
        db.ForeignKey(
            "public.workshop_departments.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    technician = db.Column(
        db.ForeignKey("public.technician.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    status = db.Column(
        db.ForeignKey(
            "public.workshop_status.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    request_approval = db.Column(db.Boolean)
    warranty_days = db.Column(db.Integer)
    exp_date_warranty = db.Column(db.Date)
    estimated_delivery_date = db.Column(db.Date)
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    station = db.Column(
        db.ForeignKey("public.stations.code", ondelete="CASCADE", onupdate="RESTRICT")
    )
    register_hour = db.Column(db.Time)
    register_date = db.Column(db.Date)
    warranty_conditions = db.Column(db.String)
    warranty_status = db.Column(
        db.ForeignKey(
            "public.workshop_warranty_status.code",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        )
    )
    reason_warranty_denied = db.Column(db.String)

    workshop_department = db.relationship(
        "WorkshopDepartment",
        primaryjoin="Workshop.department == WorkshopDepartment.code",
        backref="workshops",
    )
    station1 = db.relationship(
        "Station", primaryjoin="Workshop.station == Station.code", backref="workshops"
    )
    workshop_statu = db.relationship(
        "WorkshopStatu",
        primaryjoin="Workshop.status == WorkshopStatu.code",
        backref="workshops",
    )
    technician1 = db.relationship(
        "Technician",
        primaryjoin="Workshop.technician == Technician.code",
        backref="workshops",
    )
    user = db.relationship(
        "User", primaryjoin="Workshop.user_code == User.code", backref="workshops"
    )
    workshop_warranty_statu = db.relationship(
        "WorkshopWarrantyStatu",
        primaryjoin="Workshop.warranty_status == WorkshopWarrantyStatu.code",
        backref="workshops",
    )


class WorkshopEquipmentDetail(Workshop):
    __tablename__ = "workshop_equipment_details"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.workshop.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
    )
    equipment_code = db.Column(
        db.ForeignKey(
            "public.workshop_equipment.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    failure = db.Column(db.String)
    equipment_status = db.Column(
        db.ForeignKey(
            "public.workshop_equipment_status.code",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        )
    )
    cf_text_workshop1 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_workshop2 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_workshop3 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_workshop4 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_workshop5 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_workshop6 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_workshop7 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_workshop8 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_decimal_workshop1 = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    cf_decimal_workshop2 = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    cf_decimal_workshop3 = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    cf_bool_workshop1 = db.Column(
        db.Boolean, nullable=False, server_default=db.FetchedValue()
    )
    cf_bool_workshop2 = db.Column(
        db.Boolean, nullable=False, server_default=db.FetchedValue()
    )
    cf_bool_workshop3 = db.Column(
        db.Boolean, nullable=False, server_default=db.FetchedValue()
    )
    cf_date_workshop1 = db.Column(
        db.Date, nullable=False, server_default=db.FetchedValue()
    )
    cf_date_workshop2 = db.Column(
        db.Date, nullable=False, server_default=db.FetchedValue()
    )

    workshop_equipment = db.relationship(
        "WorkshopEquipment",
        primaryjoin="WorkshopEquipmentDetail.equipment_code == WorkshopEquipment.code",
        backref="workshop_equipment_details",
    )
    workshop_equipment_statu = db.relationship(
        "WorkshopEquipmentStatu",
        primaryjoin="WorkshopEquipmentDetail.equipment_status == WorkshopEquipmentStatu.code",
        backref="workshop_equipment_details",
    )


class WorkshopAccessory(db.Model):
    __tablename__ = "workshop_accessories"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.workshop.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    accessories_type = db.Column(
        db.ForeignKey(
            "public.workshop_accessories_types.code",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        )
    )
    code = db.Column(db.String)
    description = db.Column(db.String)

    workshop_accessories_type = db.relationship(
        "WorkshopAccessoriesType",
        primaryjoin="WorkshopAccessory.accessories_type == WorkshopAccessoriesType.code",
        backref="workshop_accessories",
    )
    workshop = db.relationship(
        "Workshop",
        primaryjoin="WorkshopAccessory.main_correlative == Workshop.correlative",
        backref="workshop_accessories",
    )


class WorkshopAccessoriesType(db.Model):
    __tablename__ = "workshop_accessories_types"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class WorkshopDepartment(db.Model):
    __tablename__ = "workshop_departments"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class WorkshopDocumentsRel(db.Model):
    __tablename__ = "workshop_documents_rel"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.workshop.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    correlative_related = db.Column(db.Integer, primary_key=True, nullable=False)
    module_related = db.Column(db.String)

    workshop = db.relationship(
        "Workshop",
        primaryjoin="WorkshopDocumentsRel.main_correlative == Workshop.correlative",
        backref="workshop_documents_rels",
    )


class WorkshopEquipment(db.Model):
    __tablename__ = "workshop_equipment"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    equipment_type = db.Column(
        db.ForeignKey(
            "public.workshop_equipment_types.code",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        )
    )
    mark = db.Column(
        db.ForeignKey(
            "public.workshop_marks.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    model = db.Column(
        db.ForeignKey(
            "public.workshop_models.code", ondelete="RESTRICT", onupdate="CASCADE"
        )
    )
    cf_text_equipment1 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_equipment2 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_equipment3 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_equipment4 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_equipment5 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_equipment6 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_equipment7 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_text_equipment8 = db.Column(
        db.String, nullable=False, server_default=db.FetchedValue()
    )
    cf_decimal_equipment1 = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    cf_decimal_equipment2 = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    cf_decimal_equipment3 = db.Column(
        db.Double(53), nullable=False, server_default=db.FetchedValue()
    )
    cf_bool_equipment1 = db.Column(
        db.Boolean, nullable=False, server_default=db.FetchedValue()
    )
    cf_bool_equipment2 = db.Column(
        db.Boolean, nullable=False, server_default=db.FetchedValue()
    )
    cf_bool_equipment3 = db.Column(
        db.Boolean, nullable=False, server_default=db.FetchedValue()
    )
    cf_date_equipment1 = db.Column(
        db.Date, nullable=False, server_default=db.FetchedValue()
    )
    cf_date_equipment2 = db.Column(
        db.Date, nullable=False, server_default=db.FetchedValue()
    )

    workshop_equipment_type = db.relationship(
        "WorkshopEquipmentType",
        primaryjoin="WorkshopEquipment.equipment_type == WorkshopEquipmentType.code",
        backref="workshop_equipments",
    )
    workshop_mark = db.relationship(
        "WorkshopMark",
        primaryjoin="WorkshopEquipment.mark == WorkshopMark.code",
        backref="workshop_equipments",
    )
    workshop_model = db.relationship(
        "WorkshopModel",
        primaryjoin="WorkshopEquipment.model == WorkshopModel.code",
        backref="workshop_equipments",
    )


class WorkshopEquipmentImage(WorkshopEquipment):
    __tablename__ = "workshop_equipment_image"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_code = db.Column(
        db.ForeignKey(
            "public.workshop_equipment.code", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
    )
    image_type = db.Column(db.String)
    product_image = db.Column(db.LargeBinary)


class WorkshopEquipmentStatu(db.Model):
    __tablename__ = "workshop_equipment_status"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class WorkshopEquipmentType(db.Model):
    __tablename__ = "workshop_equipment_types"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class WorkshopMark(db.Model):
    __tablename__ = "workshop_marks"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class WorkshopModel(db.Model):
    __tablename__ = "workshop_models"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class WorkshopNotification(db.Model):
    __tablename__ = "workshop_notification"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.workshop.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    emission_date = db.Column(db.Date)
    notification_type = db.Column(
        db.ForeignKey(
            "public.workshop_notification_type.code",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        )
    )
    notified_by = db.Column(db.String)
    notified_received_by = db.Column(db.String)
    status = db.Column(
        db.ForeignKey(
            "public.workshop_notification_status.code",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        )
    )
    description = db.Column(db.String)

    workshop = db.relationship(
        "Workshop",
        primaryjoin="WorkshopNotification.main_correlative == Workshop.correlative",
        backref="workshop_notifications",
    )
    workshop_notification_type = db.relationship(
        "WorkshopNotificationType",
        primaryjoin="WorkshopNotification.notification_type == WorkshopNotificationType.code",
        backref="workshop_notifications",
    )
    workshop_notification_statu = db.relationship(
        "WorkshopNotificationStatu",
        primaryjoin="WorkshopNotification.status == WorkshopNotificationStatu.code",
        backref="workshop_notifications",
    )


class WorkshopNotificationStatu(db.Model):
    __tablename__ = "workshop_notification_status"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class WorkshopNotificationType(db.Model):
    __tablename__ = "workshop_notification_type"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class WorkshopStatu(db.Model):
    __tablename__ = "workshop_status"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    background = db.Column(db.String)
    foreground = db.Column(db.String)


class WorkshopTechnicalReport(db.Model):
    __tablename__ = "workshop_technical_report"
    __table_args__ = {"schema": "public", "extend_existing": True}

    main_correlative = db.Column(
        db.ForeignKey(
            "public.workshop.correlative", ondelete="CASCADE", onupdate="CASCADE"
        ),
        primary_key=True,
        nullable=False,
    )
    line = db.Column(
        db.Integer, primary_key=True, nullable=False, server_default=db.FetchedValue()
    )
    emission_date = db.Column(db.Date)
    description = db.Column(db.String)
    technician = db.Column(
        db.ForeignKey("public.technician.code", ondelete="RESTRICT", onupdate="CASCADE")
    )

    workshop = db.relationship(
        "Workshop",
        primaryjoin="WorkshopTechnicalReport.main_correlative == Workshop.correlative",
        backref="workshop_technical_reports",
    )
    technician1 = db.relationship(
        "Technician",
        primaryjoin="WorkshopTechnicalReport.technician == Technician.code",
        backref="workshop_technical_reports",
    )


class WorkshopType(db.Model):
    __tablename__ = "workshop_types"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class WorkshopWarrantyStatu(db.Model):
    __tablename__ = "workshop_warranty_status"
    __table_args__ = {"schema": "public", "extend_existing": True}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class ProductsFailure(db.Model):
    __tablename__ = "products_failures"
    __table_args__ = (
        db.UniqueConstraint("product_code", "store_code"),
        {"schema": "toolbox"},
    )

    correlative = db.Column(
        db.Integer, primary_key=True
    )
    product_code = db.Column(db.ForeignKey("public.products.code"), nullable=False)
    store_code = db.Column(db.ForeignKey("public.store.code"), nullable=False)
    minimal_stock = db.Column(db.Integer, nullable=False)
    maximum_stock = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100))

    product = db.relationship(
        "Product",
        primaryjoin="ProductsFailure.product_code == Product.code",
        backref="products_failures",
    )
    store = db.relationship(
        "Store",
        primaryjoin="ProductsFailure.store_code == Store.code",
        backref="products_failures",
    )


class TxProfile(db.Model):
    __tablename__ = "profile"
    __table_args__ = {"schema": "toolbox"}

    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)
    menus_config = db.Column(db.String, nullable=False, default="[]")

    @property
    def menus_list(self):
        """Convierte el texto de la DB en una lista de Python"""
        try:
            return json.loads(self.menus_config) if self.menus_config else []
        except:
            return []

    @menus_list.setter
    def menus_list(self, value):
        """Convierte la lista de Python en texto para la DB"""
        self.menus_config = json.dumps(value)


class TxMenu(db.Model):
    __tablename__ = "menus"
    __table_args__ = {"schema": "toolbox"}
    code = db.Column(db.String, primary_key=True)
    description = db.Column(db.String)


class UserProfile(db.Model):
    __tablename__ = "user_profile"
    __table_args__ = {"schema": "toolbox"}

    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    profile_code = db.Column(
        db.ForeignKey("toolbox.profile.code", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=False,
        nullable=False,
    )


class ProductsCounterHistory(db.Model):
    __tablename__ = "products_counter_history"
    __table_args__ = {"schema": "toolbox"}

    # PK autonumérica: SQLAlchemy creará la identidad/serial
    correlative = db.Column(db.Integer, primary_key=True)

    # Documentos de inventario asociados (carga / descarga generados por el conteo)
    # Nombres de columna en BD: load_operation_correlative / down_operation_correlative
    # Nombres de atributo en Python: operation_correlative_up / operation_correlative_down
    operation_correlative_up = db.Column(
        "load_operation_correlative",
        db.ForeignKey(
            "public.inventory_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=True,
    )

    operation_correlative_down = db.Column(
        "down_operation_correlative",
        db.ForeignKey(
            "public.inventory_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=True,
    )

    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )

    store_code = db.Column(
        db.ForeignKey("public.store.code", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )

    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )

    # Identificador lógico del conteo (permite agrupar productos de un mismo conteo)
    count_batch_id = db.Column(db.String(50), index=True, nullable=True)

    count_date = db.Column(db.Date, nullable=False)

    system_qty = db.Column(db.Double(53), nullable=False)
    counted_qty = db.Column(db.Double(53), nullable=False)
    difference = db.Column(db.Double(53), nullable=False)
    observation = db.Column(db.String)

    # Relaciones de conveniencia
    load_operation = db.relationship(
        "InventoryOperation",
        primaryjoin="ProductsCounterHistory.operation_correlative_up == InventoryOperation.correlative",
        foreign_keys=[operation_correlative_up],
        backref="products_counter_history_load",
    )

    download_operation = db.relationship(
        "InventoryOperation",
        primaryjoin="ProductsCounterHistory.operation_correlative_down == InventoryOperation.correlative",
        foreign_keys=[operation_correlative_down],
        backref="products_counter_history_download",
    )

    product = db.relationship(
        "Product",
        primaryjoin="ProductsCounterHistory.product_code == Product.code",
        backref="products_counter_history",
    )
    store = db.relationship(
        "Store",
        primaryjoin="ProductsCounterHistory.store_code == Store.code",
        backref="products_counter_history",
    )
    user = db.relationship(
        "User",
        primaryjoin="ProductsCounterHistory.user_code == User.code",
        backref="products_counter_history",
    )


class InventoryOperationPackage(db.Model):
    __tablename__ = "inventory_operation_package"
    __table_args__ = (
        db.UniqueConstraint("operation_correlative", "package_number"),
        db.CheckConstraint("status IN ('OPEN', 'CLOSED', 'VOID')"),
        {"schema": "toolbox"},
    )

    correlative = db.Column(db.Integer, primary_key=True)
    operation_correlative = db.Column(
        db.ForeignKey(
            "public.inventory_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    package_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), nullable=False, server_default="OPEN")
    opened_at = db.Column(
        db.DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    opened_user = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    closed_at = db.Column(db.DateTime)
    closed_user = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    locked_at = db.Column(db.DateTime)

    inventory_operation = db.relationship(
        "InventoryOperation",
        primaryjoin="InventoryOperationPackage.operation_correlative == InventoryOperation.correlative",
        backref="operation_packages",
    )
    opened_by = db.relationship(
        "User",
        primaryjoin="InventoryOperationPackage.opened_user == User.code",
        foreign_keys=[opened_user],
        backref="opened_inventory_packages",
    )
    closed_by = db.relationship(
        "User",
        primaryjoin="InventoryOperationPackage.closed_user == User.code",
        foreign_keys=[closed_user],
        backref="closed_inventory_packages",
    )


class InventoryOperationPackageDetail(db.Model):
    __tablename__ = "inventory_operation_package_detail"
    __table_args__ = (
        db.UniqueConstraint("package_correlative", "product_code"),
        db.CheckConstraint("packed_amount > 0"),
        {"schema": "toolbox"},
    )

    correlative = db.Column(db.Integer, primary_key=True)
    package_correlative = db.Column(
        db.ForeignKey(
            "toolbox.inventory_operation_package.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    packed_amount = db.Column(db.Double(53), nullable=False)
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_user = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )

    package = db.relationship(
        "InventoryOperationPackage",
        primaryjoin="InventoryOperationPackageDetail.package_correlative == InventoryOperationPackage.correlative",
        backref="package_details",
    )
    product = db.relationship(
        "Product",
        primaryjoin="InventoryOperationPackageDetail.product_code == Product.code",
        backref="inventory_operation_package_details",
    )
    user = db.relationship(
        "User",
        primaryjoin="InventoryOperationPackageDetail.updated_user == User.code",
        backref="inventory_operation_package_details",
    )


class InventoryOperationCheckingProgress(db.Model):
    __tablename__ = "inventory_operation_checking_progress"
    __table_args__ = (
        db.UniqueConstraint(
            "operation_correlative",
            "user_code",
            "product_code",
            name="uq_inventory_operation_checking_progress",
        ),
        {"schema": "toolbox"},
    )

    correlative = db.Column(db.Integer, primary_key=True)
    operation_correlative = db.Column(
        db.ForeignKey(
            "public.inventory_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    original_amount = db.Column(db.Double(53), nullable=False)
    counted_amount = db.Column(db.Double(53), nullable=False)
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    inventory_operation = db.relationship(
        "InventoryOperation",
        primaryjoin="InventoryOperationCheckingProgress.operation_correlative == InventoryOperation.correlative",
        backref="checking_progress_entries",
    )
    user = db.relationship(
        "User",
        primaryjoin="InventoryOperationCheckingProgress.user_code == User.code",
        backref="inventory_operation_checking_progress_entries",
    )
    product = db.relationship(
        "Product",
        primaryjoin="InventoryOperationCheckingProgress.product_code == Product.code",
        backref="inventory_operation_checking_progress_entries",
    )


class InventoryOperationReceptionProgress(db.Model):
    __tablename__ = "inventory_operation_reception_progress"
    __table_args__ = (
        db.UniqueConstraint(
            "operation_correlative",
            "user_code",
            "product_code",
            name="uq_inventory_operation_reception_progress",
        ),
        {"schema": "toolbox"},
    )

    correlative = db.Column(db.Integer, primary_key=True)
    operation_correlative = db.Column(
        db.ForeignKey(
            "public.inventory_operation.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    counted_amount = db.Column(db.Double(53), nullable=False)
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    inventory_operation = db.relationship(
        "InventoryOperation",
        primaryjoin="InventoryOperationReceptionProgress.operation_correlative == InventoryOperation.correlative",
        backref="reception_progress_entries",
    )
    user = db.relationship(
        "User",
        primaryjoin="InventoryOperationReceptionProgress.user_code == User.code",
        backref="inventory_operation_reception_progress_entries",
    )
    product = db.relationship(
        "Product",
        primaryjoin="InventoryOperationReceptionProgress.product_code == Product.code",
        backref="inventory_operation_reception_progress_entries",
    )


class ShoppingProductsParam(db.Model):
    __tablename__ = "shopping_products_params"
    __table_args__ = {"schema": "toolbox"}

    correlative = db.Column(db.Integer, primary_key=True)
    code = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    minimum_stock = db.Column("min_shopping", db.Double(53), nullable=False)
    maximum_stock = db.Column("max_shopping", db.Double(53), nullable=False)
    update_at = db.Column(
        db.DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    product = db.relationship(
        "Product",
        primaryjoin="ShoppingProductsParam.code == Product.code",
        backref="shopping_products_params",
    )


class ShoppingProductsParamsHistory(db.Model):
    __tablename__ = "shopping_products_params_history"
    __table_args__ = {"schema": "toolbox"}

    correlative = db.Column(db.Integer, primary_key=True)
    main_correlative = db.Column(
        db.ForeignKey(
            "toolbox.shopping_products_params.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    user_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    register_date = db.Column(
        db.DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    shopping_products_param = db.relationship(
        "ShoppingProductsParam",
        primaryjoin="ShoppingProductsParamsHistory.main_correlative == ShoppingProductsParam.correlative",
        backref="history_entries",
    )
    user = db.relationship(
        "User",
        primaryjoin="ShoppingProductsParamsHistory.user_code == User.code",
        backref="shopping_products_params_history_entries",
    )


class PurchaseReviewList(db.Model):
    __tablename__ = "purchase_review_lists"
    __table_args__ = (
        db.CheckConstraint(
            "list_type IN ('PARAMETERS_GENERATED','PROVIDER_SUBMISSION','USER_MANUAL')",
            name="ck_purchase_review_lists_type",
        ),
        db.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','REVIEWED','APPROVED','REJECTED')",
            name="ck_purchase_review_lists_status",
        ),
        {"schema": "toolbox"},
    )

    correlative = db.Column(db.Integer, primary_key=True)
    list_type = db.Column(db.String(32), nullable=False)
    provider_code = db.Column(
        db.ForeignKey("public.provider.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    created_by = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    buyer_code = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    reference = db.Column(db.String)
    status = db.Column(db.String(32), nullable=False, server_default="DRAFT")
    provider_notes = db.Column(db.String)
    buyer_notes = db.Column(db.String)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    submitted_at = db.Column(db.DateTime)
    reviewed_at = db.Column(db.DateTime)

    provider = db.relationship(
        "Provider",
        primaryjoin="PurchaseReviewList.provider_code == Provider.code",
        backref="purchase_review_lists",
    )
    creator = db.relationship(
        "User",
        primaryjoin="PurchaseReviewList.created_by == User.code",
        backref="created_purchase_review_lists",
    )
    buyer = db.relationship(
        "User",
        primaryjoin="PurchaseReviewList.buyer_code == User.code",
        backref="assigned_purchase_review_lists",
    )


class PurchaseReviewListItem(db.Model):
    __tablename__ = "purchase_review_list_items"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('PENDING','ACCEPTED','REJECTED')",
            name="ck_purchase_review_list_items_status",
        ),
        {"schema": "toolbox"},
    )

    correlative = db.Column(db.Integer, primary_key=True)
    main_correlative = db.Column(
        db.ForeignKey(
            "toolbox.purchase_review_lists.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    unit = db.Column(
        db.ForeignKey("public.products_units.correlative", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    requested_amount = db.Column(db.Double(53), nullable=False, server_default="0")
    unitary_cost = db.Column(db.Double(53), nullable=False, server_default="0")
    status = db.Column(db.String(16), nullable=False, server_default="PENDING")
    rejected_reason = db.Column(db.String)
    reviewed_by = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    reviewed_at = db.Column(db.DateTime)
    note = db.Column(db.String)

    review_list = db.relationship(
        "PurchaseReviewList",
        primaryjoin="PurchaseReviewListItem.main_correlative == PurchaseReviewList.correlative",
        backref="items",
    )
    product = db.relationship(
        "Product",
        primaryjoin="PurchaseReviewListItem.product_code == Product.code",
        backref="purchase_review_list_items",
    )
    unit_detail = db.relationship(
        "ProductsUnit",
        primaryjoin="PurchaseReviewListItem.unit == ProductsUnit.correlative",
        backref="purchase_review_list_items",
    )
    reviewer = db.relationship(
        "User",
        primaryjoin="PurchaseReviewListItem.reviewed_by == User.code",
        backref="reviewed_purchase_review_list_items",
    )


class PurchaseReviewNewProductItem(db.Model):
    __tablename__ = "purchase_review_new_product_items"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('PENDING','ACCEPTED','REJECTED')",
            name="ck_purchase_review_new_product_items_status",
        ),
        {"schema": "toolbox"},
    )

    correlative = db.Column(db.Integer, primary_key=True)
    main_correlative = db.Column(
        db.ForeignKey(
            "toolbox.purchase_review_lists.correlative",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    proposed_description = db.Column(db.String, nullable=False)
    proposed_main_code = db.Column(db.String)
    proposed_reference = db.Column(db.String)
    proposed_mark_code = db.Column(
        db.ForeignKey("public.marks.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    proposed_department_code = db.Column(
        db.ForeignKey("public.department.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    proposed_unit_code = db.Column(
        db.ForeignKey("public.units.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    requested_amount = db.Column(db.Double(53), nullable=False, server_default="0")
    unitary_cost = db.Column(db.Double(53), nullable=False, server_default="0")
    provider_note = db.Column(db.String)
    status = db.Column(db.String(16), nullable=False, server_default="PENDING")
    rejected_reason = db.Column(db.String)
    reviewed_by = db.Column(
        db.ForeignKey("public.users.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    reviewed_at = db.Column(db.DateTime)
    approved_product_code = db.Column(
        db.ForeignKey("public.products.code", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )

    review_list = db.relationship(
        "PurchaseReviewList",
        primaryjoin="PurchaseReviewNewProductItem.main_correlative == PurchaseReviewList.correlative",
        backref="new_product_items",
    )
    mark = db.relationship(
        "Mark",
        primaryjoin="PurchaseReviewNewProductItem.proposed_mark_code == Mark.code",
        backref="purchase_review_new_product_items",
    )
    department = db.relationship(
        "Department",
        primaryjoin="PurchaseReviewNewProductItem.proposed_department_code == Department.code",
        backref="purchase_review_new_product_items",
    )
    unit = db.relationship(
        "Unit",
        primaryjoin="PurchaseReviewNewProductItem.proposed_unit_code == Unit.code",
        backref="purchase_review_new_product_items",
    )
    reviewer = db.relationship(
        "User",
        primaryjoin="PurchaseReviewNewProductItem.reviewed_by == User.code",
        backref="reviewed_purchase_review_new_product_items",
    )
    approved_product = db.relationship(
        "Product",
        primaryjoin="PurchaseReviewNewProductItem.approved_product_code == Product.code",
        backref="approved_purchase_review_new_product_items",
    )


class ProviderRegistration(db.Model):
    __tablename__ = "provider_registrations"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'BLOCKED')",
            name="ck_provider_registrations_status",
        ),
        {"schema": "toolbox"},
    )

    code = db.Column(db.String, primary_key=True, nullable=False)
    description = db.Column(db.String, nullable=False)
    address = db.Column(db.String, nullable=False)
    provider_id = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    phone = db.Column(db.String, nullable=False)
    contact = db.Column(db.String, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    registered_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    status = db.Column(db.String(30), nullable=False, server_default="PENDING")
