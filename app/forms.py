from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, TextAreaField, SelectField,
    BooleanField, SubmitField, HiddenField,
)
from wtforms.validators import (
    DataRequired, Length, Optional, Email, EqualTo, ValidationError,
)

from .models import ROLE_LABELS, ACCESS_LABELS, ACCESS_NONE, ACCESS_READ, ACCESS_WRITE


class LoginForm(FlaskForm):
    username = StringField('Benutzername', validators=[DataRequired(), Length(max=80)])
    password = PasswordField('Passwort', validators=[DataRequired()])
    remember = BooleanField('Angemeldet bleiben')
    submit = SubmitField('Anmelden')


class PageForm(FlaskForm):
    title = StringField('Titel', validators=[DataRequired(), Length(max=200)])
    parent_id = SelectField('Uebergeordnete Seite (optional)', coerce=int, validators=[Optional()])
    tags = StringField('Schlagworte (Komma-getrennt)', validators=[Optional(), Length(max=400)])
    content = TextAreaField('Inhalt', validators=[Optional()])
    comment = StringField('Aenderungsnotiz (optional)', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Speichern')


class MovePageForm(FlaskForm):
    target_space = SelectField('Ziel-Bereich', coerce=int, validators=[DataRequired()])
    parent_id = SelectField('Uebergeordnete Seite (im Ziel-Bereich)', coerce=int, validators=[Optional()])
    submit = SubmitField('Verschieben')


class PageTemplateForm(FlaskForm):
    name = StringField('Name der Vorlage', validators=[DataRequired(), Length(max=120)])
    description = StringField('Kurzbeschreibung', validators=[Optional(), Length(max=255)])
    title_hint = StringField('Vorgeschlagener Seitentitel (optional)', validators=[Optional(), Length(max=200)])
    content = TextAreaField('Vorlagen-Inhalt (Markdown)', validators=[Optional()])
    submit = SubmitField('Speichern')


class SpaceForm(FlaskForm):
    name = StringField('Name des Bereichs', validators=[DataRequired(), Length(max=120)])
    slug = StringField('Kurzname / URL (optional)', validators=[Optional(), Length(max=80)])
    parent_id = SelectField('Uebergeordneter Bereich (optional)', coerce=int, validators=[Optional()])
    description = TextAreaField('Beschreibung', validators=[Optional(), Length(max=500)])
    default_access = SelectField(
        'Standardzugriff fuer eingeloggte Nutzer',
        choices=[
            (ACCESS_NONE, ACCESS_LABELS[ACCESS_NONE]),
            (ACCESS_READ, ACCESS_LABELS[ACCESS_READ]),
            (ACCESS_WRITE, ACCESS_LABELS[ACCESS_WRITE]),
        ],
        default=ACCESS_NONE,
    )
    submit = SubmitField('Speichern')


class UserForm(FlaskForm):
    username = StringField('Benutzername', validators=[DataRequired(), Length(max=80)])
    display_name = StringField('Anzeigename', validators=[Optional(), Length(max=120)])
    email = StringField('E-Mail (optional)', validators=[Optional(), Email(), Length(max=255)])
    role = SelectField(
        'Globale Rolle',
        choices=[(k, v) for k, v in ROLE_LABELS.items()],
    )
    is_active = BooleanField('Aktiv', default=True)
    password = PasswordField(
        'Passwort',
        validators=[Optional(), Length(min=8, message='Mindestens 8 Zeichen.')],
    )
    password2 = PasswordField(
        'Passwort wiederholen',
        validators=[Optional(), EqualTo('password', message='Passwoerter stimmen nicht ueberein.')],
    )
    submit = SubmitField('Speichern')

    def __init__(self, *args, require_password=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._require_password = require_password

    def validate_password(self, field):
        if self._require_password and not field.data:
            raise ValidationError('Bitte ein Passwort vergeben.')


class MembershipForm(FlaskForm):
    user_id = SelectField('Nutzer', coerce=int, validators=[DataRequired()])
    access = SelectField(
        'Zugriff',
        choices=[
            (ACCESS_READ, ACCESS_LABELS[ACCESS_READ]),
            (ACCESS_WRITE, ACCESS_LABELS[ACCESS_WRITE]),
        ],
    )
    submit = SubmitField('Hinzufuegen')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Aktuelles Passwort', validators=[DataRequired()])
    password = PasswordField(
        'Neues Passwort',
        validators=[DataRequired(), Length(min=8, message='Mindestens 8 Zeichen.')],
    )
    password2 = PasswordField(
        'Neues Passwort wiederholen',
        validators=[DataRequired(), EqualTo('password', message='Passwoerter stimmen nicht ueberein.')],
    )
    submit = SubmitField('Passwort aendern')


class ConfirmForm(FlaskForm):
    """Leeres Formular nur fuer CSRF-geschuetzte POST-Aktionen (loeschen etc.)."""
    submit = SubmitField('Bestaetigen')
