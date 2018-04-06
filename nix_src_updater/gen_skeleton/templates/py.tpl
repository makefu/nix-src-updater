{ lib, fetchPypi, buildPythonPackage,
{% for dep in deps %}
, {{ dep }}
{% endfor %}
}:

buildPythonPackage rec {
  pname = "{{name}}";
  version = "{{version}};

  src = fetchPypi {
    inherit pname version;
    sha256 = "{{sha256|default=3f9334c39cb39c74319895fb5f3df84bf32d52fc75da1a5b358709b21c1abfef}}";
  };

  propagatedBuildInputs = [
   {% for dep in inputs['build'] %} {{ dep }}{% endfor %}
  ];

  checkInputs = [
   {% for dep in inputs['check'] %} {{ dep }}{% endfor %}
  ];

  meta = with lib; {
    description = "{{description}}";
    homepage = "{{url}}";
    license = licenses.{{license}};
    maintainers = with maintainers; [ {{maintainer|default=}} ];
  };
}
