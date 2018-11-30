pipeline {
    agent any

    stages {
        stage('Fetch SCM') {
            steps {
                checkout scm
            }
        }
        stage('Build and push image') {
            agent { node { label 'docker' } }
            steps {
                script {
                    dockerBuild 'hub.ops.ikats.org/operator-fetcher'
                }
            }
        }
    }
}
