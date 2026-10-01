# Convention : le terminal renvoie aussi l'écho de la commande tapée. On coupe
# les mots attendus avec "" dans la commande (rcl""py) pour que seul le
# résultat réel contienne le mot entier (rclpy).


def test_student_gets_a_ros_terminal(student, hub):
    name = student()
    out = hub.run(name, "ros2 pkg list | grep -x rcl\"\"py")
    assert "rclpy" in out
