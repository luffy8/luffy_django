from rest_framework import serializers

class DegreeCourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    course_img = serializers.CharField()
    brief = serializers.CharField()
    total_scholarship = serializers.IntegerField()
    mentor_compensation_bonus = serializers.IntegerField()
    period = serializers.IntegerField()
    prerequisite = serializers.CharField()
