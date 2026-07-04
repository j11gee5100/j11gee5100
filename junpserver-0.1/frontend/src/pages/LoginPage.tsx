import { useState } from 'react'
import { Button, Card, Form, Input, Typography, Alert, Space, message } from 'antd'
import { AxiosError } from 'axios'
import { useAuth } from '../auth/AuthContext'

const { Title, Text } = Typography

function loginErrorMessage(error: unknown) {
  if (error instanceof AxiosError) {
    const status = error.response?.status
    const code = error.response?.data?.code
    if (status === 401 || code === 'INVALID_CREDENTIALS') return '用户名或密码错误，请重新输入。'
    if (status === 403 || code === 'USER_DISABLED') return '该账号已被禁用，请联系管理员。'
    return error.response?.data?.message || '登录失败，请稍后重试。'
  }
  return '登录失败，请检查网络或后端服务。'
}

export default function LoginPage() {
  const auth = useAuth()
  const [form] = Form.useForm()
  const [errorText, setErrorText] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    const values = await form.validateFields()
    setErrorText('')
    setSubmitting(true)
    try {
      await auth.login(values.username, values.password)
      message.success('登录成功')
    } catch (error) {
      const text = loginErrorMessage(error)
      setErrorText(text)
      message.error(text)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#f5f7fb' }}>
      <Card style={{ width: 420 }}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <div>
            <Title level={3} style={{ marginBottom: 4 }}>OpsPaw 登录</Title>
            <Text type="secondary">请先使用账号密码登录，再进入对应权限页面。</Text>
          </div>
          {errorText && <Alert type="error" showIcon message={errorText} />}
          <Form form={form} layout="vertical" onFinish={submit} onValuesChange={() => setErrorText('')}>
            <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}><Input autoFocus /></Form.Item>
            <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}><Input.Password onPressEnter={submit} /></Form.Item>
            <Button type="primary" block htmlType="submit" loading={submitting}>登录</Button>
          </Form>
        </Space>
      </Card>
    </div>
  )
}
