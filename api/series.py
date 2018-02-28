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



class MyLevelCharField(serializers.CharField):
    """ 自定义用用于个性化显示课程level的字段

    """
    def to_representation(self, value):
        return ['初级', '中级', '高级'][value]

class MyPricePolicyField(serializers.CharField):
    def to_representation(self, value):
        result = []
        for obj in value:
            result.append({
                'id': obj.pk,
                'price': obj.price,
                'valid_period': obj.get_valid_period_display()
            })
        return result

class CourseSectionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)



class MyChapterSectionField(serializers.CharField):
    def to_representation(self, value):
        result = []
        for obj in value:
            result.append({
                'id': obj.pk,
                'chapter': obj.chapter,
                'name': obj.name,
                'section': CourseSectionSerializer(instance=obj.coursesections.all(), many=True).data
            })
        return result

class MyCouseOutlineField(serializers.CharField):
    def to_representation(self, value):
        result = []
        for obj in value:
            result.append({
                'title': obj.title,
                'content': obj.content,
            })
        return result

class MyOfftenQuestionField(serializers.CharField):
    def to_representation(self, value):
        result = []
        new_value = models.OftenAskedQuestion.objects.filter(object_id=value.id, content_type_id=13)
        print(new_value)
        for obj in new_value:
            result.append({
                'question': obj.question,
                "answoer": obj.answer,
            })
        return result



class CourseSerializers(serializers.Serializer):
    """ 普通课程对应序列化类

    """
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=128)
    brief = serializers.CharField(max_length=2048)
    level = MyLevelCharField(max_length=32)

class CourseDetailSerializers(serializers.Serializer):
    course_slogan = serializers.CharField(max_length=125)
    # video_brief_link = serializers.CharField(max_length=255)
    level = MyLevelCharField(source="course.level")
    period = serializers.IntegerField(source="course.period")
    price_policy = MyPricePolicyField(source="course.price_policy.all")
    # courseChapter_chpter = MyCourseCapterField(source="course.coursechapters.all")      # todo 无法获取数据
    brief = serializers.CharField(source="course.brief")
    why_study = serializers.CharField(max_length=4096)
    what_to_study_brief = serializers.CharField(max_length=1028)
    course_outline = MyCouseOutlineField(source="courseoutline_set.all")
    career_improvement = serializers.CharField()
    prerequisite = serializers.CharField()
    offten_asked_question = MyOfftenQuestionField(source="course")
    CourseChapter = MyChapterSectionField(source="course.coursechapters.all")

