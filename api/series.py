from rest_framework import serializers
from api import models

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.OftenAskedQuestion
        fields = ('question', 'answer')

class MycoursesField(serializers.CharField):
    def to_representation(self, value):
        ret = []
        for course in value:
            outlines = course.coursedetail.courseoutline_set.all()
            teachers = course.coursedetail.teachers.all()
            ret.append({
                'name':course.name,
                'brief':course.brief,
                'detail':course.coursedetail.id,
                'outlines':[{'title':x.title,'order':x.order,'content':x.content,} for x in outlines],
                'teachers':[{'name':x.name,'brief':x.brief} for x in teachers],

            })
        return ret


class DegreeCourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    course_img = serializers.CharField()
    brief = serializers.CharField()
    total_scholarship = serializers.IntegerField()
    mentor_compensation_bonus = serializers.IntegerField()
    period = serializers.IntegerField()
    prerequisite = serializers.CharField()
    questions = serializers.SerializerMethodField()
    courses = MycoursesField(source="course_set.all")

    def get_questions(self, obj):
        questions = models.OftenAskedQuestion.objects.filter(object_id=obj.id,content_type_id=20)
        ser = QuestionSerializer(instance=questions,many=True)
        return ser.data
