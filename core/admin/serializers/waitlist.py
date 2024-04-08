from rest_framework import serializers
from core.auth.models.waitlist import WaitlistEntry

class WaitlistEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = WaitlistEntry
        fields = ['email', 'full_name', 'description', 'id', 'admin_granted_access','created','updated']
        read_only_fields = ['email', 'full_name','description','id','admin_granted_access','created','updated']


class WaitlistEntryApprovalSerializer(serializers.ModelSerializer):
    entries = WaitlistEntrySerializer(many=True)

    class Meta:
        model = WaitlistEntry
        fields = ['email', 'full_name', 'description', 'id', 'admin_granted_access','created','updated']
        read_only_fields = ['email', 'full_name','description','id','admin_granted_access','created','updated']