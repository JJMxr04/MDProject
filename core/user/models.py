import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.http import Http404
from core.abstract.models import AbstractModel, AbstractManager
import os
from django.contrib.auth.hashers import make_password, check_password
from core.blog.writer.models import Tag
import random
import string


def user_avatar_upload_path(instance, filename):
    # File will be uploaded to MEDIA_ROOT/avatars/<username>/<filename>
    return os.path.join('avatars', instance.username, filename)


class UserManager(BaseUserManager, AbstractManager):
    def get_object_by_public_id(self, public_id):
        try:
            instance = self.get(public_id=public_id)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return Http404

    def get_object_by_email(self, email):
        try:
            instance = self.get(email=email)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return Http404

    def create_user(self, username, email, password=None, portal_password=None, **kwargs):
        if username is None:
            raise TypeError('Users must have a username.')
        if email is None:
            raise TypeError('Users must have an email.')

        user = self.model(username=username, email=self.normalize_email(email), **kwargs)
        user.set_password(password)
        user.save(using=self._db)

        # Assign user to "Portal Group"
        portal_group, created = Group.objects.get_or_create(name='Portal Group')
        user.groups.add(portal_group)

        return user

    def create_user_ex(self, username, first, last, email, password=None, **kwargs):
        if username is None:
            raise TypeError('Users must have a username.')
        if email is None:
            raise TypeError('Users must have an email.')
        if password is None:
            raise TypeError('User must have a password.')

        user = self.model(username=username, first_name=first, last_name=last, email=self.normalize_email(email),
                          **kwargs)
        user.set_password(password)
        user.save(using=self._db)

        # Assign user to "Portal Group"
        portal_group, created = Group.objects.get_or_create(name='Portal Group')
        user.groups.add(portal_group)

        return user

    def create_superuser(self, username, email, password, **kwargs):
        if password is None:
            raise TypeError('Superusers must have a password.')
        if email is None:
            raise TypeError('Superusers must have an email.')
        if username is None:
            raise TypeError('Superusers must have a username.')

        user = self.create_user(username, email, password, **kwargs)
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)

        return user

    def make_user_staff(self, user):
        user.is_staff = True
        user.save()

    def make_user_admin(self, user):
        user.is_staff = True
        user.is_admin = True
        user.save()

    def get_by_friend_code(self, friend_code):
        try:
            instance = self.get(friend_code=friend_code)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return Http404


class User(AbstractBaseUser, AbstractModel, PermissionsMixin):
    public_id = models.UUIDField(db_index=True, unique=True, default=uuid.uuid4, editable=False)
    username = models.CharField(db_index=True, max_length=255, unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(db_index=True, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_writer= models.BooleanField(default=False)
    activated_link = models.BooleanField(default=False)
    bio = models.TextField(null=True)
    avatar = models.ImageField(null=True, upload_to=user_avatar_upload_path)
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)
    tags = models.ManyToManyField(Tag, related_name='users', blank=True,verbose_name="What leagues do you plan on making predictions?")
    writer_description = models.TextField(null=True)
    stripe_account_id = models.CharField(max_length=255)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    friends = models.ManyToManyField(
        'self',
        symmetrical=True,
        blank=True,
        related_name='user_friends'
    )
    friend_code = models.CharField(max_length=8, unique=True, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = UserManager()

    def __str__(self):
        return f"{self.email}"

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    def add_friend(self, user):
        """Add a new friend"""
        if user != self:
            self.friends.add(user)
            
    def remove_friend(self, user):
        """Remove a friend"""
        self.friends.remove(user)
    
    def get_friends(self):
        """Return QuerySet of all friends"""
        return self.friends.all()
    
    def is_friend(self, user):
        """Check if given user is a friend"""
        return self.friends.filter(id=user.id).exists()

    def save(self, *args, **kwargs):
        if not self.friend_code:
            self.friend_code = self.generate_friend_code()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_friend_code():
        """Generate a random 8-character friend code"""
        while True:
            # Generate code: 8 characters, uppercase letters and numbers
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            # Check if code already exists
            if not User.objects.filter(friend_code=code).exists():
                return code
    
    @classmethod
    def find_by_friend_code(cls, code):
        """Find a user by their friend code"""
        try:
            return cls.objects.get(friend_code=code)
        except cls.DoesNotExist:
            return None

    def regenerate_friend_code(self):
        """Generate a new friend code and save it"""
        self.friend_code = self.generate_friend_code()
        self.save(update_fields=['friend_code'])
        return self.friend_code



